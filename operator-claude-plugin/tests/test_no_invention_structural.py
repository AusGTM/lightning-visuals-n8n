"""Tests for extraction.py's ambiguity aggregation and D-07 enforcement (Task 2).

Ceiling this file deliberately does NOT overstate (24-CONTEXT.md D-03, 24-RESEARCH.md's
STRUCT-04 failure-mode row): this tests the STRUCTURAL half of STRUCT-04 only — that a
record flagged uncertain for a field by an ambiguity is rejected if its row nonetheless
carries a value for that same field. It is the only invention Python can mechanically
detect. It does NOT and cannot verify that an accepted value is TRUE; the truthfulness
of an extraction is a prompt contract 24-03's SKILL.md carries, not a code guarantee.
"""
import copy
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import extraction  # noqa: E402


def _record(row, provenance=None):
    return {
        "row": row,
        "provenance": provenance
        if provenance is not None
        else {"input": "pasted_text", "locator": "line 1"},
    }


def test_ambiguity_naming_a_field_present_with_a_value_rejects_the_record():
    """A record flagged uncertain for 'jobtitle' yet whose row still carries a jobtitle
    value is a contradiction — the extraction said it was unsure, then filled it anyway.
    STRUCT-04 forbids exactly this: reject, don't dispatch a guess."""
    artifact = {
        "records": [_record({"email": "a@b.c", "jobtitle": "CEO"})],
        "ambiguities": [
            {
                "record_index": 0,
                "field": "jobtitle",
                "reason": "text was blurry, could be CEO or CFO",
            }
        ],
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert "jobtitle" in result.rejected[0]["reason"]


def test_ambiguity_on_the_only_identity_field_produces_a_rejected_row_absent_from_accepted():
    """Per D-07 an unconfirmed ambiguity leaves the value absent — so if 'email' is the
    only identity path this record has, its row correctly has no 'email' key at all, and
    it fails the identity pre-flight (not the D-07 contradiction check) and is rejected,
    never dispatched half-known."""
    artifact = {
        "records": [_record({"jobtitle": "CEO"})],
        "ambiguities": [
            {
                "record_index": 0,
                "field": "email",
                "reason": "email address was cut off at the edge of the screenshot",
            }
        ],
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert "identity" in result.rejected[0]["reason"]


def test_accepted_record_whose_ambiguity_names_a_field_simply_lacks_that_field():
    """The common, non-contradictory case: the row correctly omits the field an
    ambiguity names, and the record dispatches normally without it."""
    artifact = {
        "records": [_record({"email": "a@b.c"})],
        "ambiguities": [
            {"record_index": 0, "field": "jobtitle", "reason": "unreadable in the image"}
        ],
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 1
    assert "jobtitle" not in result.accepted[0]["row"]
    assert result.ambiguities == [
        {"record_index": 0, "field": "jobtitle", "reason": "unreadable in the image"}
    ]


def test_validate_with_no_ambiguities_returns_empty_list_not_a_missing_key():
    """The preview renders the ambiguity block unconditionally; an absent key would read
    as a crash rather than 'nothing to report'."""
    artifact = {"records": [_record({"email": "a@b.c"})]}

    result = extraction.validate(artifact)

    assert result.ambiguities == []


def test_two_validate_runs_over_the_same_artifact_return_equal_results():
    """Nothing about the batch depends on order of processing or a random tiebreak — a
    preview that reorders itself between runs is one the operator cannot diff."""
    artifact = {
        "records": [
            _record(
                {"email": "same@example.com", "jobtitle": "CEO"},
                {"input": "screenshot_1.png", "locator": "row 1"},
            ),
            _record(
                {"email": "same@example.com", "jobtitle": "CTO"},
                {"input": "screenshot_2.png", "locator": "row 4"},
            ),
            _record(
                {"firstname": "Cara", "lastname": "Chen", "company": "Acme"},
                {"input": "screenshot_1.png", "locator": "row 8"},
            ),
            _record(
                {"email": "cara@other.example", "firstname": "Cara", "lastname": "Chen"},
                {"input": "screenshot_2.png", "locator": "row 9"},
            ),
        ]
    }

    result_1 = extraction.validate(copy.deepcopy(artifact))
    result_2 = extraction.validate(copy.deepcopy(artifact))

    assert result_1.accepted == result_2.accepted
    assert result_1.rejected == result_2.rejected
    assert result_1.dropped_keys == result_2.dropped_keys
    assert result_1.ambiguities == result_2.ambiguities
    assert result_1.collapses == result_2.collapses


def test_no_ambiguity_resolution_or_application_function_exists_in_extraction_module():
    """D-07's strongest structural guarantee: there is no apply-correction or
    confirm-ambiguity function anywhere in this module. The only way a value enters a
    row is validate() reading it off the artifact Claude wrote; resolving an ambiguity
    means the operator answers in chat, Claude rewrites the artifact, and validate() runs
    again — never a Python function that flips a flag or fills a value in place.

    D-59-08 (operator ruling, 2026-08-28): the ruling widened WHERE propose-mode is
    used (a failed identity check now also classifies into `resolvable`) — it did NOT
    widen where a Python function may enter a value into a row. This guarantee now
    covers the resolution surface as well as the ambiguity surface: the four original
    forbidden substrings are UNCHANGED, and four more are added for the equivalent
    identity-resolution names, so a `fill_identity`/`apply_resolution`/
    `confirm_resolution`/`resolve_identity` function would fail this test exactly the
    way an ambiguity-filling one always has."""
    import inspect

    forbidden_substrings = [
        "resolve_ambig", "apply_ambig", "confirm_ambig", "fill_ambig",
        "fill_identity", "apply_resolution", "confirm_resolution", "resolve_identity",
    ]
    # Only functions this module defines itself — resolve_mapping_path is imported from
    # preview.py and resolves a config PATH, not an ambiguity; excluding imports keeps
    # this check about extraction.py's own surface, not names it happens to import.
    function_names = [
        name
        for name, obj in inspect.getmembers(extraction, inspect.isfunction)
        if inspect.getmodule(obj) is extraction
    ]

    for name in function_names:
        lowered = name.lower()
        for bad in forbidden_substrings:
            assert bad not in lowered, (
                f"found a function whose name suggests it applies or resolves an "
                f"ambiguity or identity resolution: {name} — per D-07/D-59-08 there is "
                f"no such path"
            )


def test_resolution_sources_is_a_closed_set_and_an_unrecognized_source_rejects():
    """The structural half of D-59-08's anti-laundering control (T-59-20), living next
    to the structural half of the no-invention control: RESOLUTION_SOURCES is a closed
    frozenset of exactly the four legitimate identifiers, and a record naming a source
    outside it is rejected rather than accepted unlabelled."""
    assert isinstance(extraction.RESOLUTION_SOURCES, frozenset)
    assert extraction.RESOLUTION_SOURCES == {
        "hubspot_lookup",
        "operator_statement",
        "provider_result",
        "same_row_derivation",
    }

    artifact = {
        "records": [
            _record(
                {"firstname": "Cara", "lastname": "Chen", "company": "Acme"},
                {"input": "pasted_text", "locator": "line 1"},
            )
        ]
    }
    artifact["records"][0]["resolutions"] = [
        {"field": "company", "source": "an_unrecognized_source", "detail": "?"}
    ]

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert "an_unrecognized_source" in result.rejected[0]["reason"]
