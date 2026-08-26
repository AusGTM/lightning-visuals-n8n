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
