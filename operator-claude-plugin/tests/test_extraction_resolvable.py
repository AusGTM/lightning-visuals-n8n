"""Tests for D-59-08's identity-gate conversion (Task 2, 59-05): refuse-and-stop becomes
refuse-and-classify-as-proposable, with unlaunderable provenance via a closed
resolution-source vocabulary (`extraction.RESOLUTION_SOURCES`).

The structural guarantee that no Python function fills a value into a row lives in
`test_no_invention_structural.py`, extended in the same commit as this file. These tests
cover the CLASSIFICATION (`resolvable`) and PROVENANCE (`resolutions`) behavior layered
on top of the unchanged identity gate.
"""
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import extraction  # noqa: E402
import preview  # noqa: E402


def _record(row, provenance=None, record_type=None, resolutions=None):
    """Mirrors test_no_invention_structural.py's `_record()` shape, extended with the
    two optional record-level keys D-59-08 adds."""
    rec = {
        "row": row,
        "provenance": provenance
        if provenance is not None
        else {"input": "pasted_text", "locator": "line 1"},
    }
    if record_type is not None:
        rec["record_type"] = record_type
    if resolutions is not None:
        rec["resolutions"] = resolutions
    return rec


def test_contact_missing_company_is_rejected_and_also_reported_resolvable():
    """A contact row with only firstname/lastname is rejected AS TODAY, and ALSO
    appears in `resolvable` naming `company` as the missing field — the exact shape of
    the LinkedIn-sourced row that dead-ended in the Phase 53 walk."""
    artifact = {"records": [_record({"firstname": "Cara", "lastname": "Chen"})]}

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert "identity" in result.rejected[0]["reason"]
    assert len(result.resolvable) == 1
    entry = result.resolvable[0]
    assert entry["index"] == 0
    assert entry["record_type"] == "contacts"
    assert "company" in entry["missing"]


def test_company_missing_name_is_rejected_and_also_reported_resolvable():
    """A company row with no name is rejected as today, and also appears in
    `resolvable` naming `name`."""
    artifact = {
        "records": [_record({"domain": "example.org"}, record_type="companies")]
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert len(result.resolvable) == 1
    entry = result.resolvable[0]
    assert entry["record_type"] == "companies"
    assert "name" in entry["missing"]


def test_malformed_record_is_rejected_and_absent_from_resolvable():
    """A record with no usable resolution path (here: an unrecognized record_type) is
    rejected and does NOT appear in `resolvable` — a classification that fires for
    everything classifies nothing."""
    artifact = {
        "records": [
            {
                "row": {"email": "a@b.c"},
                "provenance": {"input": "x", "locator": "y"},
                "record_type": "not-a-real-type",
            }
        ]
    }

    result = extraction.validate(artifact)

    assert len(result.rejected) == 1
    assert result.resolvable == []


def test_record_carrying_a_valid_resolution_is_accepted_and_carries_it_through():
    """A record carrying a `resolutions` entry naming a legitimate source, whose row
    already has the resolved field's value, is ACCEPTED — and the accepted entry
    carries the resolution through so a downstream reader can see it was resolved."""
    artifact = {
        "records": [
            _record(
                {"firstname": "Cara", "lastname": "Chen", "company": "Acme"},
                resolutions=[
                    {
                        "field": "company",
                        "source": "hubspot_lookup",
                        "detail": "matched by domain",
                    }
                ],
            )
        ]
    }

    result = extraction.validate(artifact)

    assert result.rejected == []
    assert len(result.accepted) == 1
    assert result.accepted[0]["resolutions"] == [
        {"field": "company", "source": "hubspot_lookup", "detail": "matched by domain"}
    ]


def test_resolution_naming_a_source_outside_the_closed_vocabulary_is_rejected():
    """A record whose `resolutions` names a source outside RESOLUTION_SOURCES is
    REJECTED, with a reason naming the bad source — the anti-laundering control."""
    artifact = {
        "records": [
            _record(
                {"firstname": "Cara", "lastname": "Chen", "company": "Acme"},
                resolutions=[
                    {
                        "field": "company",
                        "source": "claude_recall",
                        "detail": "I remember this company",
                    }
                ],
            )
        ]
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert "claude_recall" in result.rejected[0]["reason"]


def test_resolution_naming_a_field_the_row_does_not_carry_is_rejected():
    """A record whose `resolutions` names a field its row does not actually carry is
    REJECTED."""
    artifact = {
        "records": [
            _record(
                {"firstname": "Cara", "lastname": "Chen"},
                resolutions=[
                    {"field": "company", "source": "hubspot_lookup", "detail": "matched"}
                ],
            )
        ]
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert "company" in result.rejected[0]["reason"]


def test_resolved_field_named_by_an_ambiguity_still_rejects_under_d07():
    """A record whose `resolutions` names a field an ambiguity ALSO names is REJECTED
    by the unchanged D-07 contradiction check — being resolved does not exempt a field
    from it."""
    artifact = {
        "records": [
            _record(
                {"firstname": "Cara", "lastname": "Chen", "company": "Acme"},
                resolutions=[
                    {"field": "company", "source": "hubspot_lookup", "detail": "matched"}
                ],
            )
        ],
        "ambiguities": [
            {
                "record_index": 0,
                "field": "company",
                "reason": "unsure this is the right company",
            }
        ],
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert "company" in result.rejected[0]["reason"]


def test_build_extracted_preview_returns_resolvable_key_and_keeps_duck_typing():
    """`build_extracted_preview` returns a `resolvable` key, and still works when handed
    an object with only the four original attributes (the duck-typing contract)."""

    class Shim:
        accepted = []
        rejected = [{"index": 0, "reason": "no identity present"}]
        dropped_keys = []
        ambiguities = []

    out = preview.build_extracted_preview(Shim())
    assert out["resolvable"] == []

    artifact = {"records": [_record({"firstname": "Cara", "lastname": "Chen"})]}
    result = extraction.validate(artifact)
    out2 = preview.build_extracted_preview(result)
    assert len(out2["resolvable"]) == 1
