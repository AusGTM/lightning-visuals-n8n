"""The CLIENT half of the list-envelope contract (D-19).

Why this file exists. 25-04 built the client envelope and 25-03 built the backend that
reads it, and they disagreed. The client sent a flat
``{"providers": [...], "list": "<name>", "objectType": "contacts"}`` while
``n8n/code/listExpansion.js`` reads ``isPlainObject(body.list)`` and then ``body.list.name``
/ ``body.list.objectType``. A string is non-null, so a flat envelope PASSES the
``IF List Input`` gate and is then refused by every request with "the enrichment request
named no list" — the entire list lane dead, while both plans' own suites stayed green
because each tested only its own side of the webhook.

One literal, pinned from both sides. The JS twin is ``tests/n8n/listEnvelopeContract.test.mjs``
and it asserts ``expandListToEvents`` ACCEPTS exactly this. This file asserts
``build_envelope`` PRODUCES exactly this. Change the shape on either side and one of the two
fails — which is the property that was missing, not more coverage of either half.
"""
import enrichment

# EXACTLY what tests/n8n/listEnvelopeContract.test.mjs feeds to expandListToEvents.
# Keep byte-identical with the JS twin.
CLIENT_ENVELOPE = {
    "providers": ["lusha"],
    "list": {"name": "New Targets.xlsx", "objectType": "contacts"},
}


def test_build_envelope_produces_exactly_the_contract_literal():
    envelope = enrichment.build_envelope(
        {"list": "New Targets.xlsx", "object_type": "contacts"}, ["lusha"]
    )
    assert envelope == CLIENT_ENVELOPE


def test_the_list_key_is_a_nested_object_never_a_bare_string():
    envelope = enrichment.build_envelope(
        {"list": "New Targets.xlsx", "object_type": "contacts"}, ["lusha"]
    )
    assert isinstance(envelope["list"], dict), (
        "a bare string here is the exact bug: it passes the backend's IF List Input gate "
        "and is then refused by every request"
    )
    assert "objectType" not in envelope, (
        "objectType belongs inside `list`; a sibling key is the flat shape returning"
    )


def test_object_type_is_normalized_inside_the_nested_object():
    # The backend accepts contacts/companies/0-1/0-2, but the client should still send the
    # normalized long form so the two agree on one spelling rather than two.
    envelope = enrichment.build_envelope(
        {"list": "Some list", "object_type": "contact"}, []
    )
    assert envelope["list"]["objectType"] == "contacts"


def test_a_record_id_envelope_carries_no_list_key_at_all():
    envelope = enrichment.build_envelope(
        {"record_ids": ["1", "2"], "object_type": "companies"}, ["apollo"]
    )
    assert "list" not in envelope
    assert envelope["events"] == [
        {"objectId": "1", "objectType": "companies"},
        {"objectId": "2", "objectType": "companies"},
    ]
