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


# =====================================================================================
# Task 2: match_batch
# =====================================================================================

def _plan_of(n_rows, ceiling):
    spec = preingest.build_rows_spec(_rows(n_rows))
    return chunking.plan_chunks(spec, ceiling)


def _item(row_id, tier="none"):
    return {"row_id": row_id, "mode": "propose", "action": "proposed",
            "match": {"tier": tier, "candidates": []}}


def test_match_batch_issues_exactly_two_calls_in_plan_order(
        fake_config, stub_post_transport_factory):
    plan = _plan_of(4, ceiling=2)  # two chunks of two rows
    responses = [
        [_item("row-1"), _item("row-2")],
        [_item("row-3"), _item("row-4")],
    ]
    stub = stub_post_transport_factory(responses=list(responses))

    outcome = preingest.match_batch(plan, fake_config, transport=stub)

    assert len(stub.calls) == 2
    assert not outcome.unchecked_row_ids
    assert outcome.failed_batch is None


def test_a_chunk_whose_transport_raises_does_not_stop_the_run(
        fake_config, stub_post_transport_factory):
    plan = _plan_of(4, ceiling=2)
    stub = stub_post_transport_factory(responses=[
        RuntimeError("dead endpoint"),
        [_item("row-3"), _item("row-4")],
    ])

    outcome = preingest.match_batch(plan, fake_config, transport=stub)

    assert len(stub.calls) == 2, "the second chunk must still be called"
    assert outcome.unchecked_row_ids == {"row-1", "row-2"}


def test_partition_unchecked_ids_and_response_row_ids_cover_the_plan_with_no_overlap(
        fake_config, stub_post_transport_factory):
    plan = _plan_of(4, ceiling=2)
    stub = stub_post_transport_factory(responses=[
        RuntimeError("dead endpoint"),
        [_item("row-3"), _item("row-4")],
    ])

    outcome = preingest.match_batch(plan, fake_config, transport=stub)

    response_row_ids = {item["row_id"] for item in outcome.responses}
    all_row_ids = {f"row-{i}" for i in range(1, 5)}
    assert outcome.unchecked_row_ids | response_row_ids == all_row_ids
    assert outcome.unchecked_row_ids & response_row_ids == set()


def test_the_backends_whole_batch_refusal_marks_the_whole_chunk_unchecked_with_its_own_reason(
        fake_config, stub_post_transport_factory):
    plan = _plan_of(2, ceiling=2)  # one chunk
    refusal = [{"outcome": "refused", "reason": "Request carries 2 events, more than "
                "this backend can enrich in one request", "events": [],
                "object_type": "unknown"}]
    stub = stub_post_transport_factory(responses=[refusal])

    outcome = preingest.match_batch(plan, fake_config, transport=stub)

    assert outcome.unchecked_row_ids == {"row-1", "row-2"}
    assert any("Request carries 2 events" in reason for reason in outcome.failure_reasons)


def test_the_outcomes_failed_batch_resends_through_plan_chunks_as_the_original_rows(
        fake_config, stub_post_transport_factory):
    plan = _plan_of(4, ceiling=2)
    stub = stub_post_transport_factory(responses=[
        RuntimeError("dead endpoint"),
        [_item("row-3"), _item("row-4")],
    ])

    outcome = preingest.match_batch(plan, fake_config, transport=stub)

    resend_plan = chunking.plan_chunks(outcome.failed_batch, ceiling=2)
    resent_ids = [row["row_id"] for chunk in resend_plan.chunks for row in chunk["rows"]]
    assert resent_ids == ["row-1", "row-2"]


def test_when_nothing_fails_unchecked_is_empty_and_failed_batch_is_absent(
        fake_config, stub_post_transport_factory):
    plan = _plan_of(2, ceiling=2)
    stub = stub_post_transport_factory(responses=[[_item("row-1"), _item("row-2")]])

    outcome = preingest.match_batch(plan, fake_config, transport=stub)

    assert outcome.unchecked_row_ids == frozenset()
    assert outcome.failed_batch is None


def test_match_batch_never_catches_or_imports_not_armed_error_there_is_nothing_to_arm():
    """`fetch_matches`/`match_batch` never raise `NotArmedError` in the first place —
    there is no `armed` parameter anywhere in this module — so nothing here should
    ever import or catch it."""
    import ast

    tree = ast.parse((PLUGIN_ROOT / "scripts" / "preingest.py").read_text())
    imported_names = {
        alias.asname or alias.name
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    caught_names = {
        name.id
        for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)
        for name in ([node.type] if isinstance(node.type, ast.Name) else [])
    }
    assert "NotArmedError" not in imported_names
    assert "NotArmedError" not in caught_names


# =====================================================================================
# Task 3: classify_matches
# =====================================================================================

_MEDIUM_CANDIDATE = {
    "hs_object_id": "12345", "firstname": "Jane", "lastname": "Doe",
    "email": "jane@x.com", "jobtitle": "Director", "company": "GCTC",
}


def _rows_and_ids(n):
    spec = preingest.build_rows_spec(_rows(n))
    return spec["rows"]


def test_high_tier_buckets_auto_matched_and_carries_hs_object_id():
    rows = _rows_and_ids(1)
    response = [{
        "row_id": rows[0]["row_id"], "action": "proposed", "hs_object_id": "999",
        "match": {"tier": "high"},
    }]
    result = preingest.classify_matches(rows, response)
    assert len(result["auto_matched"]) == 1
    assert result["auto_matched"][0]["hs_object_id"] == "999"
    assert not result["proposed"] and not result["unmatched"] and not result["unchecked"]


def test_medium_tier_buckets_proposed_with_candidates_carried_through():
    rows = _rows_and_ids(1)
    response = [{
        "row_id": rows[0]["row_id"], "action": "proposed",
        "match": {"tier": "medium", "candidates": [_MEDIUM_CANDIDATE]},
    }]
    result = preingest.classify_matches(rows, response)
    assert len(result["proposed"]) == 1
    assert result["proposed"][0]["candidates"] == [_MEDIUM_CANDIDATE]
    assert result["proposed"][0]["ambiguous"] is False


def test_two_or_more_medium_candidates_is_ambiguous_and_none_is_pre_selected():
    rows = _rows_and_ids(1)
    other = {**_MEDIUM_CANDIDATE, "hs_object_id": "67890"}
    response = [{
        "row_id": rows[0]["row_id"], "action": "proposed",
        "match": {"tier": "medium", "candidates": [_MEDIUM_CANDIDATE, other]},
    }]
    result = preingest.classify_matches(rows, response)
    entry = result["proposed"][0]
    assert entry["ambiguous"] is True
    assert len(entry["candidates"]) == 2
    assert "selected" not in entry and "preferred" not in entry


def test_none_tier_buckets_unmatched():
    rows = _rows_and_ids(1)
    response = [{"row_id": rows[0]["row_id"], "action": "proposed", "match": {"tier": "none"}}]
    result = preingest.classify_matches(rows, response)
    assert len(result["unmatched"]) == 1


def test_unknown_tier_buckets_unchecked_never_unmatched():
    rows = _rows_and_ids(1)
    response = [{"row_id": rows[0]["row_id"], "action": "proposed", "match": {"tier": "unknown"}}]
    result = preingest.classify_matches(rows, response)
    assert len(result["unchecked"]) == 1
    assert not result["unmatched"]


def test_a_row_id_absent_from_the_response_buckets_unchecked_never_dropped():
    rows = _rows_and_ids(3)
    response = [
        {"row_id": rows[0]["row_id"], "action": "proposed", "match": {"tier": "none"}},
        {"row_id": rows[2]["row_id"], "action": "proposed", "match": {"tier": "none"}},
    ]
    result = preingest.classify_matches(rows, response)
    assert len(result["unchecked"]) == 1
    assert result["unchecked"][0]["row_id"] == rows[1]["row_id"]
    assert len(result["unmatched"]) == 2


def test_a_response_item_matching_no_input_row_is_reported_never_attached():
    rows = _rows_and_ids(1)
    response = [
        {"row_id": rows[0]["row_id"], "action": "proposed", "match": {"tier": "none"}},
        {"row_id": "row-does-not-exist", "action": "proposed", "match": {"tier": "high"}},
    ]
    result = preingest.classify_matches(rows, response)
    assert result["unknown_response_row_ids"] == ["row-does-not-exist"]
    assert len(result["auto_matched"]) == 0


def test_two_response_items_with_the_same_row_id_is_a_refusal_not_last_one_wins():
    rows = _rows_and_ids(1)
    response = [
        {"row_id": rows[0]["row_id"], "action": "proposed", "match": {"tier": "none"}},
        {"row_id": rows[0]["row_id"], "action": "proposed", "match": {"tier": "high"}},
    ]
    with pytest.raises(preingest.ClassifyError):
        preingest.classify_matches(rows, response)


def test_the_four_bucket_sizes_sum_to_the_input_row_count():
    rows = _rows_and_ids(4)
    response = [
        {"row_id": rows[0]["row_id"], "action": "proposed", "match": {"tier": "high"}, "hs_object_id": "1"},
        {"row_id": rows[1]["row_id"], "action": "proposed",
         "match": {"tier": "medium", "candidates": [_MEDIUM_CANDIDATE]}},
        {"row_id": rows[2]["row_id"], "action": "proposed", "match": {"tier": "none"}},
        # rows[3] absent from the response entirely -> unchecked
    ]
    result = preingest.classify_matches(rows, response)
    total = sum(len(result[bucket]) for bucket in
                ("auto_matched", "proposed", "unmatched", "unchecked"))
    assert total == len(rows)


def test_a_proposed_candidates_key_set_is_exactly_the_six_shipped_names():
    rows = _rows_and_ids(1)
    response = [{
        "row_id": rows[0]["row_id"], "action": "proposed",
        "match": {"tier": "medium", "candidates": [_MEDIUM_CANDIDATE]},
    }]
    result = preingest.classify_matches(rows, response)
    candidate = result["proposed"][0]["candidates"][0]
    assert set(candidate) == set(preingest.CANDIDATE_KEYS)
    assert "lastmodifieddate" not in candidate


def test_lastmodifieddate_appears_nowhere_in_preingest_source():
    source = (PLUGIN_ROOT / "scripts" / "preingest.py").read_text()
    assert "lastmodifieddate" not in source


def test_needs_match_review_appears_nowhere_in_preingest_source():
    """Deliberately unhandled — write-path-only action, never sent by this client
    (which always requests mode:"propose"). See preingest.classify_matches's
    docstring and 37-03-SUMMARY.md."""
    source = (PLUGIN_ROOT / "scripts" / "preingest.py").read_text()
    assert "needs_match_review" not in source


def test_classify_matches_respects_a_pre_seeded_unchecked_set_from_match_batch():
    rows = _rows_and_ids(2)
    response = [{"row_id": rows[1]["row_id"], "action": "proposed", "match": {"tier": "none"}}]
    result = preingest.classify_matches(
        rows, response, unchecked_row_ids={rows[0]["row_id"]},
    )
    assert len(result["unchecked"]) == 1
    assert result["unchecked"][0]["row_id"] == rows[0]["row_id"]
    assert len(result["unmatched"]) == 1


# =====================================================================================
# 37-04 Task 1: apply_match_decisions
# =====================================================================================

_CAND_A = {**_MEDIUM_CANDIDATE, "hs_object_id": "111"}
_CAND_B = {**_MEDIUM_CANDIDATE, "hs_object_id": "222"}


def _classified_with_one_proposed(n_candidates=1):
    rows = _rows_and_ids(1)
    candidates = [_CAND_A, _CAND_B][:n_candidates]
    response = [{
        "row_id": rows[0]["row_id"], "action": "proposed",
        "match": {"tier": "medium", "candidates": candidates},
    }]
    return preingest.classify_matches(rows, response), rows[0]["row_id"]


def test_confirming_a_proposals_own_candidate_moves_it_to_auto_matched_with_that_id():
    classified, row_id = _classified_with_one_proposed()
    result = preingest.apply_match_decisions(classified, {row_id: "111"})

    assert not result["proposed"]
    confirmed = [e for e in result["auto_matched"] if e["row_id"] == row_id]
    assert len(confirmed) == 1
    assert confirmed[0]["hs_object_id"] == "111"


def test_declining_a_proposal_moves_it_to_unmatched():
    classified, row_id = _classified_with_one_proposed()
    result = preingest.apply_match_decisions(
        classified, {row_id: preingest.DECLINE_MATCH}
    )

    assert not result["proposed"]
    assert any(e["row_id"] == row_id for e in result["unmatched"])
    assert not any(e["row_id"] == row_id for e in result["auto_matched"])


def test_a_proposed_row_absent_from_resolved_stays_proposed_and_unresolved():
    classified, row_id = _classified_with_one_proposed()
    result = preingest.apply_match_decisions(classified, {})

    assert len(result["proposed"]) == 1
    assert result["proposed"][0]["row_id"] == row_id


def test_a_decision_naming_a_row_that_was_never_proposed_raises_naming_the_row():
    classified, _row_id = _classified_with_one_proposed()
    with pytest.raises(preingest.MatchDecisionError) as exc:
        preingest.apply_match_decisions(classified, {"row-does-not-exist": "111"})
    assert "row-does-not-exist" in str(exc.value)


def test_a_decision_naming_a_foreign_candidate_id_raises_naming_row_and_candidate():
    classified, row_id = _classified_with_one_proposed()
    with pytest.raises(preingest.MatchDecisionError) as exc:
        preingest.apply_match_decisions(classified, {row_id: "999-not-a-candidate"})
    message = str(exc.value)
    assert row_id in message
    assert "999-not-a-candidate" in message


def test_all_or_nothing_one_invalid_entry_means_no_valid_entry_takes_effect():
    rows = _rows_and_ids(2)
    response = [
        {"row_id": rows[0]["row_id"], "action": "proposed",
         "match": {"tier": "medium", "candidates": [_CAND_A]}},
        {"row_id": rows[1]["row_id"], "action": "proposed",
         "match": {"tier": "medium", "candidates": [_CAND_B]}},
    ]
    classified = preingest.classify_matches(rows, response)
    original_auto_matched_len = len(classified["auto_matched"])
    original_proposed_len = len(classified["proposed"])

    resolved = {
        rows[0]["row_id"]: "111",              # valid
        rows[1]["row_id"]: "not-a-candidate",   # invalid
    }

    with pytest.raises(preingest.MatchDecisionError):
        preingest.apply_match_decisions(classified, resolved)

    # The valid entry (rows[0]) must not have taken effect anywhere, and the
    # caller's own classified dict must be untouched.
    assert len(classified["auto_matched"]) == original_auto_matched_len
    assert len(classified["proposed"]) == original_proposed_len
    assert not any(e["row_id"] == rows[0]["row_id"] for e in classified["auto_matched"])


def test_an_ambiguous_row_is_resolvable_only_by_naming_one_of_its_own_candidates():
    classified, row_id = _classified_with_one_proposed(n_candidates=2)
    assert classified["proposed"][0]["ambiguous"] is True

    result = preingest.apply_match_decisions(classified, {row_id: "222"})
    confirmed = [e for e in result["auto_matched"] if e["row_id"] == row_id]
    assert confirmed[0]["hs_object_id"] == "222"


def test_apply_match_decisions_with_empty_resolved_returns_a_classification_equal_to_input():
    classified, _row_id = _classified_with_one_proposed()
    result = preingest.apply_match_decisions(classified, {})
    assert result == classified


def test_apply_match_decisions_does_not_mutate_the_input_classification():
    classified, row_id = _classified_with_one_proposed()
    snapshot_proposed = list(classified["proposed"])
    snapshot_auto_matched = list(classified["auto_matched"])

    preingest.apply_match_decisions(classified, {row_id: "111"})

    assert classified["proposed"] == snapshot_proposed
    assert classified["auto_matched"] == snapshot_auto_matched
