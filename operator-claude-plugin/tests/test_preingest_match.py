"""Tests for `preingest.py`'s match lane (Phase 37 Plan 03):

Task 1: `build_rows_spec` (ids minted once, before chunking) and `fetch_matches` (one
unarmed POST per chunk, visible to the AST arming guard, response-shape normalization).

Task 2: `match_batch` (sequential, skip-a-failing-chunk, `unchecked` never `unmatched`).

Task 3: `classify_matches` (four tiers, joined by `row_id`, nothing auto-picked).

Every network-shaped test uses `stub_post_transport_factory` — `fetch_matches` is
attribute-shaped (`transport=requests.post`), not module-shaped, so
`stub_module_transport_factory` (built for `dispatch_enrichment`-style bare-module
callers) does not apply here. The autouse `no_network` fixture blocks any test that
forgets to stub the transport.
"""
from pathlib import Path

import pytest

import chunking
import config_gate
import enrichment
import preingest
from dispatch import DispatchError

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _rows(n):
    return [
        {"firstname": f"First{i}", "lastname": "Doe", "company": "GCTC"}
        for i in range(n)
    ]


# =====================================================================================
# Task 1a: build_rows_spec
# =====================================================================================

def test_build_rows_spec_assigns_distinct_deterministic_ids():
    spec = preingest.build_rows_spec(_rows(3))
    ids = [row["row_id"] for row in spec["rows"]]
    assert len(set(ids)) == 3

    spec_again = preingest.build_rows_spec(_rows(3))
    assert [row["row_id"] for row in spec_again["rows"]] == ids, (
        "same input, same ids — a re-run must be comparable to its predecessor"
    )


def test_build_rows_spec_refuses_a_row_that_already_carries_a_row_id():
    rows = [{"firstname": "Jane", "lastname": "Doe", "company": "GCTC", "row_id": "r9"}]
    with pytest.raises(preingest.RowSpecError):
        preingest.build_rows_spec(rows)


def test_build_rows_spec_refuses_an_empty_rows_list():
    with pytest.raises(preingest.RowSpecError):
        preingest.build_rows_spec([])


def test_build_rows_spec_does_not_mutate_the_callers_rows():
    original = _rows(2)
    snapshot = [dict(r) for r in original]
    preingest.build_rows_spec(original)
    assert original == snapshot


def test_ids_stay_distinct_across_chunks_the_property_a_per_chunk_enumerate_would_break():
    spec = preingest.build_rows_spec(_rows(5))
    plan = chunking.plan_chunks(spec, 2)
    ids = [row["row_id"] for chunk in plan.chunks for row in chunk["rows"]]
    assert len(set(ids)) == 5


# =====================================================================================
# Task 1b: fetch_matches
# =====================================================================================

def _chunk(n, object_type="contacts"):
    spec = preingest.build_rows_spec(_rows(n))
    return {"rows": spec["rows"], "object_type": object_type}


def test_fetch_matches_records_one_call_with_propose_mode_empty_providers_one_event_per_row(
        fake_config, stub_post_transport_factory):
    stub = stub_post_transport_factory()
    chunk = _chunk(2)

    preingest.fetch_matches(chunk, fake_config, transport=stub)

    assert len(stub.calls) == 1
    body = stub.calls[0]["json"]
    assert body["mode"] == "propose"
    assert body["providers"] == []
    assert len(body["events"]) == 2


def test_every_recorded_event_key_set_is_a_subset_of_the_structural_pair_plus_match_lookup_keys(
        fake_config, stub_post_transport_factory):
    stub = stub_post_transport_factory()
    spec = preingest.build_rows_spec([{
        "firstname": "Jane", "lastname": "Doe", "company": "GCTC", "email": "jane@x.com",
        "jobtitle": "Director", "phone": "555-1234", "linkedin_url": "https://x.com/jane",
    }])
    chunk = {"rows": spec["rows"], "object_type": "contacts"}

    preingest.fetch_matches(chunk, fake_config, transport=stub)

    body = stub.calls[0]["json"]
    allowed = {"row_id", "objectType"} | set(enrichment.MATCH_LOOKUP_KEYS)
    for event in body["events"]:
        assert set(event) <= allowed, f"event carried a key outside the allowlist: {event}"
    # And the richer props specifically never crossed the boundary.
    for event in body["events"]:
        assert "phone" not in event
        assert "jobtitle" not in event
        assert "linkedin_url" not in event


def test_fetch_matches_takes_no_armed_argument():
    with pytest.raises(TypeError):
        preingest.fetch_matches({"rows": [], "object_type": "contacts"}, {}, armed=True)


def test_fetch_matches_on_a_config_missing_webhook_secret_names_the_match_step(
        stub_post_transport_factory):
    stub = stub_post_transport_factory()
    cfg = {"n8n_url": "https://fake-tenant.n8n.cloud"}

    with pytest.raises(config_gate.ConfigError) as exc:
        preingest.fetch_matches(_chunk(1), cfg, transport=stub)

    message = str(exc.value)
    assert "uploading contacts" not in message
    assert "enriching records" not in message
    assert stub.calls == []


def test_fetch_matches_accepts_a_bare_object_and_a_one_element_array_identically(
        fake_config, stub_post_transport_factory):
    item = {"row_id": "row-1", "mode": "propose", "action": "proposed",
            "match": {"tier": "none"}}

    bare = stub_post_transport_factory(responses=[item])
    wrapped = stub_post_transport_factory(responses=[[item]])

    result_bare = preingest.fetch_matches(_chunk(1), fake_config, transport=bare)
    result_wrapped = preingest.fetch_matches(_chunk(1), fake_config, transport=wrapped)

    assert result_bare == result_wrapped == [item]


def test_fetch_matches_transport_exception_never_relays_request_headers(
        fake_config, stub_post_transport_factory):
    secret_marker = fake_config["webhook_secret"]
    stub = stub_post_transport_factory(responses=[RuntimeError("boom: X-Enrichment-Secret leaked")])

    with pytest.raises(DispatchError) as exc:
        preingest.fetch_matches(_chunk(1), fake_config, transport=stub)

    assert secret_marker not in str(exc.value)
    assert "X-Enrichment-Secret" not in str(exc.value)


def test_fetch_matches_raises_dispatch_error_on_a_non_2xx_status(
        fake_config, stub_post_transport_factory):
    stub = stub_post_transport_factory(responses=[(500, {"error": "boom"})])
    with pytest.raises(DispatchError):
        preingest.fetch_matches(_chunk(1), fake_config, transport=stub)


def test_fetch_matches_raises_dispatch_error_on_an_unreadable_body(
        fake_config, stub_post_transport_factory):
    stub = stub_post_transport_factory(responses=[(200, ValueError("not json"))])
    with pytest.raises(DispatchError):
        preingest.fetch_matches(_chunk(1), fake_config, transport=stub)


# =====================================================================================
# Task 1c: refused_reason
# =====================================================================================

def test_refused_reason_detects_the_whole_batch_refusal_shape():
    refusal = [{"outcome": "refused", "reason": "too many events", "events": [],
                "object_type": "unknown"}]
    assert preingest.refused_reason(refusal) == "too many events"


def test_refused_reason_is_none_for_ordinary_per_row_items():
    items = [{"row_id": "row-1", "mode": "propose", "action": "proposed",
              "match": {"tier": "none"}}]
    assert preingest.refused_reason(items) is None


def test_refused_reason_is_none_for_an_empty_list():
    assert preingest.refused_reason([]) is None
