# tests/test_judge_reason_distribution.py
#
# Quick task 260911-anv — offline proof for scripts/judge_reason_distribution.py's
# `summarize` pure function. No network: this file never imports requests, never sets
# N8N_URL/N8N_API_KEY, and asserts nothing about `collect`/`main` (those need a live n8n
# credential and are exercised manually per the PLAN.md, not here).
import json

import scripts.judge_reason_distribution as jrd

# One hand-built runData dict covering every case the <behavior> block names:
#   - "Judge Gate" (companies lane) has TWO runs whose items must BOTH be folded.
#   - item 1: a row with two reasons (confidence_band, org_type_conflict).
#   - item 4: a capped row — reasons present, needs_judge False, judge_capped True.
#   - item 3: a row whose research candidate did not match (matched: False) — must not
#     count toward rows_research_matched even though it reached the gate.
#   - item 2: a row with an empty reasons array.
#   - item 5: a row with judge_reasons absent entirely (never a KeyError).
#   - a non-dict item sitting among item 3/4/5's real items — skipped, not raised on.
#   - a third, malformed run on "Judge Gate" (no `data` key at all) — contributes zero.
#   - "Contact Judge Gate" (contacts lane) carries one matched, one-reason row, so the
#     two-node fold and the per-lane/total split are both exercised.
FIXTURE = {
    "Judge Gate": [
        {
            "data": {
                "main": [
                    [
                        {"json": {
                            "research_candidate": {"matched": True},
                            "judge_reasons": ["confidence_band", "org_type_conflict"],
                            "needs_judge": True,
                        }},
                        {"json": {
                            "research_candidate": {"matched": True},
                            "judge_reasons": [],
                            "needs_judge": False,
                        }},
                    ]
                ]
            }
        },
        {
            "data": {
                "main": [
                    [
                        {"json": {
                            "research_candidate": {"matched": False},
                            "judge_reasons": [],
                            "needs_judge": False,
                        }},
                        {"json": {
                            "research_candidate": {"matched": True},
                            "judge_reasons": ["confidence_band"],
                            "needs_judge": False,
                            "judge_capped": True,
                        }},
                        "not-a-dict-item",
                        {"json": {
                            "research_candidate": {"matched": True},
                            # judge_reasons deliberately absent
                        }},
                    ]
                ]
            }
        },
        {"startTime": 123},  # malformed run: no "data" key at all
    ],
    "Contact Judge Gate": [
        {
            "data": {
                "main": [
                    [
                        {"json": {
                            "research_candidate": {"matched": True},
                            "judge_reasons": ["confidence_band"],
                            "needs_judge": True,
                        }},
                    ]
                ]
            }
        }
    ],
}

EXPECTED_COMPANIES = {
    "rows_through_gate": 5,
    "rows_research_matched": 4,
    "rows_with_reasons": 2,
    "rows_capped": 1,
    "by_reason": {"confidence_band": 2, "org_type_conflict": 1},
    "by_reason_set": {"confidence_band,org_type_conflict": 1, "confidence_band": 1},
}

EXPECTED_CONTACTS = {
    "rows_through_gate": 1,
    "rows_research_matched": 1,
    "rows_with_reasons": 1,
    "rows_capped": 0,
    "by_reason": {"confidence_band": 1},
    "by_reason_set": {"confidence_band": 1},
}

EXPECTED_TOTAL = {
    "rows_through_gate": 6,
    "rows_research_matched": 5,
    "rows_with_reasons": 3,
    "rows_capped": 1,
    "by_reason": {"confidence_band": 3, "org_type_conflict": 1},
    "by_reason_set": {"confidence_band,org_type_conflict": 1, "confidence_band": 2},
}


def test_summarize_folds_both_runs_and_both_lanes():
    result = jrd.summarize(FIXTURE)
    assert result["companies"] == EXPECTED_COMPANIES
    assert result["contacts"] == EXPECTED_CONTACTS
    assert result["total"] == EXPECTED_TOTAL


def test_summarize_carries_no_row_payload_or_identity_field():
    result = jrd.summarize(FIXTURE)
    serialized = json.dumps(result)
    for forbidden in (
        "research_candidate", "existingRecord", "identity_keys", "judge_request_body",
        "needs_judge",
    ):
        assert forbidden not in serialized, f"{forbidden!r} leaked into summarize() output"
    # every leaf value is an int or a reason-name string; nothing else survives.
    for lane in ("companies", "contacts", "total"):
        counts = result[lane]
        for key in ("rows_through_gate", "rows_research_matched", "rows_with_reasons", "rows_capped"):
            assert isinstance(counts[key], int)
        for reason, count in counts["by_reason"].items():
            assert isinstance(reason, str)
            assert isinstance(count, int)


def test_summarize_empty_input_never_raises_and_zeroes_out():
    result = jrd.summarize({})
    for lane in ("companies", "contacts", "total"):
        assert result[lane]["rows_through_gate"] == 0
        assert result[lane]["rows_research_matched"] == 0
        assert result[lane]["rows_with_reasons"] == 0
        assert result[lane]["rows_capped"] == 0
        assert result[lane]["by_reason"] == {}
        assert result[lane]["by_reason_set"] == {}


def test_summarize_malformed_shapes_never_raise():
    # node present but not a list
    jrd.summarize({"Judge Gate": "not-a-list"})
    # node is a list of non-dict runs
    jrd.summarize({"Judge Gate": ["not-a-dict-run", None, 42]})
    # run present but "data" is not a dict
    jrd.summarize({"Judge Gate": [{"data": "nope"}]})
    # run present, "data" is a dict but "main" is missing
    jrd.summarize({"Judge Gate": [{"data": {}}]})
    # top-level run_data itself is not a dict
    jrd.summarize(None)
    jrd.summarize([])
    jrd.summarize("nope")
