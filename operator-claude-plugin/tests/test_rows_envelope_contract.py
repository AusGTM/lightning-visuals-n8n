"""The CLIENT half of the rows-envelope contract (D-19 class).

Why this file exists. The list-envelope contract (`test_list_envelope_contract.py`)
pinned one wire shape after a field-name mismatch shipped once and killed the whole list
lane while both suites stayed green. Phase 37's rows form is the same class of risk: a
rows envelope whose event keys the backend does not read routes every row to lane
``"none"``, where the enrichment gate skips it silently, returning a clean 200 having
matched nothing.

One literal, pinned from both sides. The JS twin is
``tests/n8n/rowsEnvelopeContract.test.mjs`` and it asserts the backend's own
``parseWebhookBody`` + ``laneOf`` route this exact envelope to the MEDIUM match lane
(``"name"``). This file asserts ``enrichment.build_envelope`` PRODUCES exactly this
literal. Change the shape on either side and one of the two fails — which is the
property that was missing, not more coverage of either half.
"""
import enrichment

# EXACTLY what tests/n8n/rowsEnvelopeContract.test.mjs feeds to parseWebhookBody +
# laneOf. Keep byte-identical with the JS twin.
CLIENT_ENVELOPE = {
    "providers": [],
    "mode": "propose",
    "events": [
        {
            "row_id": "r1",
            "objectType": "contacts",
            "email": None,
            "firstname": "Jane",
            "lastname": "Doe",
            "company": "GCTC",
            # Phase 61 Plan 02 Task 3: linkedin_url widened into MATCH_LOOKUP_KEYS — every
            # event now carries it (None when the row didn't supply one). The JS twin's
            # own CLIENT_ENVELOPE literal must carry this same key or the two silently
            # drift apart, exactly the class of bug this pin exists to catch.
            "linkedin_url": None,
        }
    ],
}


def test_build_envelope_produces_exactly_the_contract_literal():
    envelope = enrichment.build_envelope(
        {
            "rows": [
                {"row_id": "r1", "firstname": "Jane", "lastname": "Doe", "company": "GCTC"}
            ],
            "object_type": "contacts",
        },
        [],
    )
    assert envelope == CLIENT_ENVELOPE


def test_the_event_projection_is_match_lookup_keys_not_the_rows_own_keys():
    envelope = enrichment.build_envelope(
        {
            "rows": [
                {
                    "row_id": "r1",
                    "firstname": "Jane",
                    "lastname": "Doe",
                    "company": "GCTC",
                    "phone": "555-1234",
                    "jobtitle": "Director",
                    "linkedin_url": "https://linkedin.example/jane",
                }
            ],
            "object_type": "contacts",
        },
        [],
    )
    event = envelope["events"][0]
    for excluded in ("phone", "jobtitle"):
        assert excluded not in event, (
            f"{excluded} crossed the boundary — only MATCH_LOOKUP_KEYS may cross it"
        )
    # Phase 61 Plan 02 Task 3 (D-61-05 CORRECTED): linkedin_url now DOES cross — proving
    # this widened by exactly one key rather than opening the tuple is what the phone/
    # jobtitle exclusion above and this inclusion together demonstrate.
    assert event["linkedin_url"] == "https://linkedin.example/jane"


def test_mode_is_propose_and_is_not_readable_from_the_spec():
    envelope = enrichment.build_envelope(
        {
            "rows": [{"row_id": "r1", "firstname": "Jane", "lastname": "Doe", "company": "GCTC"}],
            "object_type": "contacts",
            "mode": "write",  # a caller cannot smuggle write mode through a rows form
        },
        [],
    )
    assert envelope["mode"] == "propose"


def test_a_row_missing_row_id_raises():
    try:
        enrichment.build_envelope(
            {
                "rows": [{"firstname": "Jane", "lastname": "Doe", "company": "GCTC"}],
                "object_type": "contacts",
            },
            [],
        )
    except enrichment.RecordSpecError as exc:
        assert "row_id" in str(exc)
    else:
        raise AssertionError("a row without row_id must raise RecordSpecError")


def test_an_empty_rows_list_raises():
    try:
        enrichment.build_envelope({"rows": [], "object_type": "contacts"}, [])
    except enrichment.RecordSpecError:
        pass
    else:
        raise AssertionError("an empty rows list must raise RecordSpecError")


def test_object_type_normalizes_through_the_existing_table():
    envelope = enrichment.build_envelope(
        {
            "rows": [{"row_id": "r1", "firstname": "Jane", "lastname": "Doe", "company": "GCTC"}],
            "object_type": "contact",
        },
        [],
    )
    assert envelope["events"][0]["objectType"] == "contacts"


def test_events_preserve_input_order():
    envelope = enrichment.build_envelope(
        {
            "rows": [
                {"row_id": "r1", "lastname": "Doe"},
                {"row_id": "r2", "lastname": "Smith"},
                {"row_id": "r3", "lastname": "Jones"},
            ],
            "object_type": "contacts",
        },
        [],
    )
    assert [e["row_id"] for e in envelope["events"]] == ["r1", "r2", "r3"]


def test_an_empty_or_none_row_value_emits_none_never_the_string_none():
    envelope = enrichment.build_envelope(
        {
            "rows": [
                {"row_id": "r1", "firstname": "", "lastname": None, "company": "GCTC"}
            ],
            "object_type": "contacts",
        },
        [],
    )
    event = envelope["events"][0]
    assert event["firstname"] is None
    assert event["lastname"] is None
    assert event["firstname"] != "None"
    assert event["lastname"] != "None"
