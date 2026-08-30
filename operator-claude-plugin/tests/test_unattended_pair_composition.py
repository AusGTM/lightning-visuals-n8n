"""Phase 61 Plan 06 Task 2 — same-run company-id propagation (HIGH-12/REVIEW-12,
REVIEW-C17) and the REVIEW-10 client-side consumer for an ingest-lane no-company
hold.

Drives the REAL functions (`preingest.index_company_dependencies`,
`preingest.assign_same_run_company_ids`, `preingest.classify_company_resolution_hold`,
`preingest.ingest_response_needs_hold`, `preingest.hold_ingest_no_company`,
`held_queue.save`/`held_queue.load`) with only the n8n response SHAPE synthesized —
this composition never calls n8n or HubSpot.
"""
import held_queue
import preingest
import run_manifest


# =====================================================================================
# index_company_dependencies / assign_same_run_company_ids — the coalescing case
# =====================================================================================


def test_a_company_created_this_run_is_carried_forward_by_value_with_no_second_search():
    """Behavior: "A contact whose company was created earlier in the same run is
    associated using the id that create RETURNED — no second search, no waiting, no
    retry loop." Shaped exactly like `Adapt Company Create`'s own emitted item."""
    company_responses = [
        {"company_dependency_id": "newco.example", "company_id": "9700000001"},
    ]
    index = preingest.index_company_dependencies(company_responses)
    assert index == {"newco.example": "9700000001"}

    rows = [
        {"row_id": "row-1", "email": "a@newco.example", "company_domain": "newco.example"},
        {"row_id": "row-2", "email": "b@newco.example", "company_domain": "newco.example"},
    ]
    resolved, assigned = preingest.assign_same_run_company_ids(rows, index)

    assert assigned == 2, "several contacts naming the same new company coalesce onto ONE create"
    assert resolved[0]["company_id"] == "9700000001"
    assert resolved[1]["company_id"] == "9700000001"


def test_a_row_with_no_matching_dependency_is_left_untouched():
    rows = [{"row_id": "row-1", "company_domain": "unrelated.example"}]
    resolved, assigned = preingest.assign_same_run_company_ids(
        rows, {"newco.example": "9700000001"}
    )
    assert assigned == 0
    assert "company_id" not in resolved[0]


def test_a_row_that_already_carries_a_company_id_is_never_overwritten():
    rows = [{"row_id": "row-1", "company_domain": "newco.example", "company_id": "manual-1"}]
    resolved, assigned = preingest.assign_same_run_company_ids(
        rows, {"newco.example": "9700000001"}
    )
    assert assigned == 0
    assert resolved[0]["company_id"] == "manual-1"


def test_a_create_response_with_no_company_id_is_not_durable_evidence():
    """The create failed, was blocked, or predates the builder change — ignored, not
    treated as evidence of anything."""
    index = preingest.index_company_dependencies(
        [{"company_dependency_id": "newco.example", "company_id": None}]
    )
    assert index == {}


# =====================================================================================
# classify_company_resolution_hold — immediate hold vs. bounded lag vs. terminal hold
# =====================================================================================


def test_a_genuinely_absent_company_holds_the_row_immediately_regardless_of_attempt():
    """Behavior: "A contact whose company genuinely does not exist is held" — no
    waiting, whatever `attempt` is, because `has_create_evidence` is False."""
    for attempt in (0, 1, 99):
        disposition, reason = preingest.classify_company_resolution_hold(
            "no company in HubSpot matched domain nowhere.example",
            has_create_evidence=False, attempt=attempt,
        )
        assert disposition == "held"
        assert reason == "no company in HubSpot matched domain nowhere.example"


def test_a_create_evidenced_zero_hit_retries_up_to_the_bound_then_holds_naming_the_lag():
    """Behavior: "A zero-hit search WITH durable evidence that this run created that
    company is the only case allowed to be called lag, and it is held with a reason
    naming the lag after a bounded number of attempts — never retried without end.\""""
    for attempt in range(preingest.LAG_RETRY_LIMIT):
        disposition, reason = preingest.classify_company_resolution_hold(
            "no company in HubSpot matched domain newco.example",
            has_create_evidence=True, attempt=attempt,
        )
        assert disposition == "retry"
        assert reason is None

    disposition, reason = preingest.classify_company_resolution_hold(
        "no company in HubSpot matched domain newco.example",
        has_create_evidence=True, attempt=preingest.LAG_RETRY_LIMIT,
    )
    assert disposition == "held"
    assert "lag" in reason
    assert "not absence" in reason


# =====================================================================================
# REVIEW-10: an n8n-held row lands in the LOCAL held queue, with its reason
# =====================================================================================


def test_an_ingest_lane_no_company_hold_is_recognised_from_the_build_ingest_response_shape():
    held_item = {
        "action": "review", "outcome": "net_new", "contact_id": None, "hs_object_id": None,
        "email": "sam@nowhere.example", "company_id": None, "company_match": None,
        "association": "none",
        "reason": "no company in HubSpot matched domain nowhere.example",
    }
    landed_item = {
        "action": "create", "outcome": "net_new", "contact_id": "12345",
        "company_id": "9700000001", "association": "associated", "reason": None,
    }
    update_item = {
        "action": "update", "outcome": "match", "contact_id": "555",
        "company_id": None, "association": "none", "reason": None,
    }

    assert preingest.ingest_response_needs_hold(held_item) is True
    assert preingest.ingest_response_needs_hold(landed_item) is False
    assert preingest.ingest_response_needs_hold(update_item) is False, (
        "an update with nothing to associate is never held — companyLink.js's own contract"
    )


def test_an_n8n_held_row_lands_in_the_local_held_queue_with_its_reason(monkeypatch, tmp_path):
    fake_durable = tmp_path / "durable"
    fake_durable.mkdir()
    (fake_durable / "dashboard_artifact.json").write_text("{}")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(fake_durable))

    row = {"row_id": "row-9", "email": "sam@nowhere.example", "company": "Nowhere Co"}
    item = {
        "action": "review", "outcome": "net_new", "contact_id": None,
        "company_id": None, "association": "none",
        "reason": "no company in HubSpot matched domain nowhere.example",
        "company_match": None, "email": "sam@nowhere.example",
    }
    assert preingest.ingest_response_needs_hold(item)

    entry = preingest.hold_ingest_no_company(row, item)
    held_entries = held_queue.load()
    held_entries["row-9"] = entry
    held_queue.save("run-abc", held_entries)

    reloaded = held_queue.load()
    assert "row-9" in reloaded
    assert reloaded["row-9"]["reason"] == item["reason"]
    assert reloaded["row-9"]["row"]["email"] == "sam@nowhere.example"


# =====================================================================================
# The poll-loop guard (behavior line): no plugin script outside watch.py gains an
# import of time, a sleep call, or a while loop — driven for real by
# test_report_sufficiency.py's own scanner, re-run in Task 2's <verify> block; this
# test only pins that this module's OWN new code contains none of the three shapes.
# =====================================================================================


def test_this_modules_bounded_lag_mechanism_has_no_sleep_or_loop():
    import ast
    import inspect

    source = inspect.getsource(preingest.classify_company_resolution_hold)
    tree = ast.parse(source)
    assert not any(isinstance(n, ast.While) for n in ast.walk(tree))
    assert "sleep" not in source
    assert "import time" not in source
