"""Company extraction (Phase 58) — a company row alongside the existing contact lane.

Task 1 proves ONE path end to end: a company known only by its name travels
artifact -> extraction.validate() -> enrichment.build_envelope()'s companies form ->
a single companies envelope event. Later tasks in this plan extend this file with the
mixed-artifact, dedupe, D-07, and adapter-prose pins named in 58-01-PLAN.md.
"""
import extraction
import enrichment


def test_company_mapping_yaml_has_exactly_five_canonical_props():
    props = extraction.canonical_props(mapping_path=extraction.COMPANY_MAPPING_PATH)
    assert props == sorted({"name", "domain", "country", "industry", "website"})


def test_company_mapping_identity_is_name_alone():
    groups = extraction.identity_groups(mapping_path=extraction.COMPANY_MAPPING_PATH)
    assert groups == [["name"]]


def test_bare_company_name_reaches_a_companies_envelope_event():
    artifact = {
        "batch_id": "batch-58-01",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            {
                "record_type": "companies",
                "row": {"name": "Football NSW"},
                "provenance": {
                    "input": "pasted_text",
                    "locator": "line 1: 'Football NSW'",
                },
            }
        ],
        "ambiguities": [],
    }

    result = extraction.validate(artifact)

    assert result.rejected == []
    assert len(result.accepted) == 1
    assert result.accepted[0]["row"] == {"name": "Football NSW"}

    envelope = enrichment.build_envelope(
        {"companies": [{"name": result.accepted[0]["row"]["name"]}]},
        [],
    )
    assert envelope["events"] == [{"objectType": "companies", "name": "Football NSW"}]


def test_nameless_company_record_is_rejected_without_naming_contact_fields():
    artifact = {
        "batch_id": "batch-58-01b",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            {
                "record_type": "companies",
                "row": {"domain": "example.org"},
                "provenance": {"input": "pasted_text", "locator": "line 2"},
            }
        ],
        "ambiguities": [],
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    reason = result.rejected[0]["reason"]
    assert "name" in reason
    assert "email" not in reason
    assert "firstname" not in reason
    assert "lastname" not in reason


def test_absent_record_type_still_validates_against_contact_rules():
    """No `record_type` key means `contacts` (backwards compatibility, 58-01-PLAN.md
    Task 1) — every pre-Phase-58 artifact and test keeps working unchanged."""
    artifact = {
        "batch_id": "batch-58-01c",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            {
                "row": {"email": "amy@example.com"},
                "provenance": {"input": "pasted_text", "locator": "line 3"},
            }
        ],
        "ambiguities": [],
    }

    result = extraction.validate(artifact)

    assert result.rejected == []
    assert len(result.accepted) == 1
    assert result.accepted[0]["row"] == {"email": "amy@example.com"}


# =====================================================================================
# Task 2 — mixed input, one pass: both lanes in one artifact, companies first.
# =====================================================================================


def _record(row, provenance_locator, record_type=None):
    entry = {"row": row, "provenance": {"input": "pasted_text", "locator": provenance_locator}}
    if record_type is not None:
        entry["record_type"] = record_type
    return entry


def test_mixed_artifact_validates_both_lanes_in_one_pass_companies_first():
    artifact = {
        "batch_id": "batch-58-02a",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            _record({"email": "amy@example.com"}, "l1"),
            _record({"name": "Football NSW"}, "l2", record_type="companies"),
            _record({"email": "ben@example.com"}, "l3"),
            _record({"name": "Racing NSW"}, "l4", record_type="companies"),
        ],
        "ambiguities": [],
    }

    result = extraction.validate(artifact)

    assert result.rejected == []
    assert len(result.accepted) == 4
    assert [e["record_type"] for e in result.accepted] == [
        "companies",
        "companies",
        "contacts",
        "contacts",
    ]
    assert {e["row"]["name"] for e in result.accepted[:2]} == {"Football NSW", "Racing NSW"}
    assert {e["row"]["email"] for e in result.accepted[2:]} == {
        "amy@example.com",
        "ben@example.com",
    }


def test_every_accepted_entry_carries_a_record_type():
    artifact = {
        "batch_id": "batch-58-02b",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            _record({"email": "amy@example.com"}, "l1"),
            _record({"name": "Football NSW"}, "l2", record_type="companies"),
        ],
        "ambiguities": [],
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 2
    for entry in result.accepted:
        assert entry["record_type"] in ("contacts", "companies")


def test_two_identical_company_rows_collapse_to_one():
    artifact = {
        "batch_id": "batch-58-02c",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            _record({"name": "Football NSW"}, "l1", record_type="companies"),
            _record({"name": "  football nsw "}, "l2", record_type="companies"),
        ],
        "ambiguities": [],
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 1
    assert result.accepted[0]["record_type"] == "companies"


def test_company_row_and_contact_row_with_overlapping_values_never_collapse():
    """A company row and a contact row are never in the same dedupe() call — by
    construction they cannot collapse into each other, whatever their field values."""
    artifact = {
        "batch_id": "batch-58-02d",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            _record({"name": "Acme"}, "l1", record_type="companies"),
            _record({"firstname": "John", "lastname": "Doe", "company": "Acme"}, "l2"),
        ],
        "ambiguities": [],
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 2
    assert {e["record_type"] for e in result.accepted} == {"companies", "contacts"}


def test_company_record_flagging_domain_ambiguous_with_a_value_is_rejected():
    """D-07: a record whose row still carries a value for a field one of the
    artifact's own ambiguities names on that same record is a contradiction and is
    rejected, whatever record_type it carries."""
    artifact = {
        "batch_id": "batch-58-02e",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            _record(
                {"name": "Ambiguous Co", "domain": "maybe.example"}, "l1", record_type="companies"
            ),
        ],
        "ambiguities": [
            {"record_index": 0, "field": "domain", "reason": "unclear which domain is theirs"}
        ],
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert "D-07" in result.rejected[0]["reason"]


def test_extraction_contract_backwards_compat_pin_absent_record_type_routes_to_contacts():
    """The property everything else in test_extraction_contract.py depends on: a
    record with no `record_type` key is judged exactly as it is today, byte-for-byte
    the same rejection sentence, unaffected by Phase 58's company lane."""
    artifact = {
        "batch_id": "batch-58-02f",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            {"row": {}, "provenance": {"input": "pasted_text", "locator": "l1"}},
        ],
        "ambiguities": [],
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert result.rejected == [
        {
            "index": 0,
            "reason": (
                "no identity present: needs a non-blank 'email', or all "
                "three of 'firstname'/'lastname'/'company' non-blank"
            ),
        }
    ]
