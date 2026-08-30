"""Company extraction (Phase 58) — a company row alongside the existing contact lane.

Task 1 proves ONE path end to end: a company known only by its name travels
artifact -> extraction.validate() -> enrichment.build_envelope()'s companies form ->
a single companies envelope event. Task 2 extends validate() itself to be fully
type-aware over a mixed artifact. Task 3 pins extraction.md's company adapter prose
against the same config the code reads, structurally rather than by a retyped list.
"""
from pathlib import Path

import yaml

import extraction
import enrichment

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
EXTRACTION_MD = PLUGIN_ROOT / "skills" / "contact-upload" / "extraction.md"

# The six adapter headings Task 3 adds, verbatim. Structural: a test below asserts
# each exists in extraction.md by reading the file, never by re-describing the
# adapter in the test's own words.
COMPANY_ADAPTER_HEADINGS = (
    "### Company adapter: pasted freeform text",
    "### Company adapter: foreign-shaped JSON",
    "### Company adapter: a public URL",
    "### Company adapter: operator-supplied screenshots",
    "### Company adapter: a bare name list",
    "### Company adapter: a search-results-page screenshot",
)

COMPANY_CANONICAL_PROPS_HEADING = "### Company canonical props — the entire vocabulary"
COMPANY_IDENTITY_RULE_HEADING = "### Company identity rule"


def _extraction_md_text() -> str:
    return EXTRACTION_MD.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """The text from `heading` up to (not including) the next line starting with
    `#` — the same structural slicing convention test_extraction_contract.py's
    `_url_adapter_regions()` already uses, so a section can be read without
    retyping its content into the test."""
    start = text.index(heading)
    rest = text[start + len(heading):]
    next_heading = None
    for line in rest.splitlines():
        if line.startswith("#"):
            next_heading = line
            break
    end = len(text) if next_heading is None else text.index(next_heading, start)
    return text[start:end]


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


def test_mixed_batch_ambiguity_on_a_contact_survives_companies_first_reassembly():
    """CR-01 (58-REVIEW.md): an artifact-supplied ambiguity is written against the RAW
    `records` index, before validate() ever splits by type and reassembles
    companies-first. A company record ordered before the contact record it names
    must not cause the ambiguity to land on the wrong (company) row post-reassembly
    — the exact repro from 58-REVIEW.md's CR-01."""
    artifact = {
        "batch_id": "b1",
        "source": {"kind": "prose", "detail": "x"},
        "records": [
            {
                "row": {"email": "a@x.com", "jobtitle": "Snr Producer"},
                "provenance": {"input": "pasted_text", "locator": "l1"},
            },
            {
                "row": {"name": "Acme"},
                "provenance": {"input": "pasted_text", "locator": "l2"},
                "record_type": "companies",
            },
        ],
        "ambiguities": [
            {"record_index": 0, "field": "jobtitle", "reason": "title looked uncertain"}
        ],
    }

    result = extraction.validate(artifact)

    assert len(result.rejected) == 1
    assert "D-07" in result.rejected[0]["reason"]
    assert len(result.accepted) == 1
    assert result.accepted[0]["row"] == {"name": "Acme"}
    for entry in result.accepted:
        assert "_raw_index" not in entry
        assert "_raw_indices" not in entry


def test_mixed_batch_ambiguity_on_a_company_survives_contacts_first_input_order():
    """The inverse ordering: the ambiguous record is submitted second (a contact
    first, a company second) yet still targets the company by its raw index. The
    companies-first reassembly must still resolve it correctly."""
    artifact = {
        "batch_id": "b2",
        "source": {"kind": "prose", "detail": "x"},
        "records": [
            {
                "row": {"email": "a@x.com"},
                "provenance": {"input": "pasted_text", "locator": "l1"},
            },
            {
                "row": {"name": "Acme", "domain": "maybe.example"},
                "provenance": {"input": "pasted_text", "locator": "l2"},
                "record_type": "companies",
            },
        ],
        "ambiguities": [
            {"record_index": 1, "field": "domain", "reason": "unclear which domain is theirs"}
        ],
    }

    result = extraction.validate(artifact)

    assert len(result.rejected) == 1
    assert "D-07" in result.rejected[0]["reason"]
    assert len(result.accepted) == 1
    assert result.accepted[0]["row"] == {"email": "a@x.com"}


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
                "no identity present: needs a non-blank 'email', or all three of "
                "'firstname'/'lastname'/'company' non-blank, or a non-blank "
                "'linkedin_url'"
            ),
        }
    ]


def test_unrecognized_record_type_is_rejected_by_name_not_silently_coerced():
    """WR-02 (58-REVIEW.md): a near-miss spelling like 'Companies' must be a named
    rejection, not a silent fall-through to the contact lane's identity rule (which
    would give a misleading "needs email/firstname+lastname+company" reason for what
    was actually a mistyped company row)."""
    artifact = {
        "batch_id": "batch-58-wr02",
        "source": {"kind": "prose", "detail": "pasted text"},
        "records": [
            {
                "row": {"name": "Acme"},
                "provenance": {"input": "pasted_text", "locator": "l1"},
                "record_type": "Companies",
            },
        ],
        "ambiguities": [],
    }

    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    reason = result.rejected[0]["reason"]
    assert "record_type" in reason
    assert "Companies" in reason
    assert "email" not in reason


# =====================================================================================
# Task 3 — the six company source adapters: prose contract and structural pins.
# =====================================================================================


def test_all_six_company_adapter_headings_are_present():
    text = _extraction_md_text()
    for heading in COMPANY_ADAPTER_HEADINGS:
        assert heading in text, f"missing company adapter heading: {heading!r}"


def test_company_canonical_props_section_matches_the_config_file_exactly():
    """No prop list retyped as a literal here — read company_column_mapping.yaml,
    derive the same sorted(set(aliases.values())) canonical_props() itself computes,
    and assert every one of those names appears in extraction.md's own company
    canonical-props section."""
    mapping = yaml.safe_load(extraction.COMPANY_MAPPING_PATH.read_text(encoding="utf-8"))
    props = sorted(set(dict(mapping["aliases"]).values()))
    assert props == extraction.canonical_props(mapping_path=extraction.COMPANY_MAPPING_PATH)

    section = _section(_extraction_md_text(), COMPANY_CANONICAL_PROPS_HEADING)
    for prop in props:
        assert prop in section, f"canonical company prop {prop!r} not named in {COMPANY_CANONICAL_PROPS_HEADING!r}"


def test_extraction_md_documents_the_record_type_field_and_both_values():
    text = _extraction_md_text()
    assert "record_type" in text
    assert '"contacts"' in text
    assert '"companies"' in text


def test_company_identity_rule_section_matches_identity_groups():
    """The prose's stated company identity rule must match
    identity_groups(mapping_path=COMPANY_MAPPING_PATH) — a single group of one field,
    `name` — read from the config rather than retyped."""
    groups = extraction.identity_groups(mapping_path=extraction.COMPANY_MAPPING_PATH)
    assert groups == [["name"]]

    section = _section(_extraction_md_text(), COMPANY_IDENTITY_RULE_HEADING)
    (only_field,) = groups[0]
    assert only_field in section
    assert "alone" in section
    # No contact identity field is named as an alternative way to satisfy a company's
    # identity — companies have exactly one identity group, unlike contacts' two.
    assert "email" not in section
    assert "firstname" not in section


def test_profile_page_never_becomes_a_company_domain_is_documented():
    text = _extraction_md_text()
    assert "linkedin" in text.lower()
    assert "never recorded as that company" in text or "never recorded as the company" in text
