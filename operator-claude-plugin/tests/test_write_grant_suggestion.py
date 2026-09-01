"""Tests for `write_grant.envelope()`/`plan_grant()`'s suggestion allowance (Phase 62,
D-62-11/12/13/14 — Task 2's checkpoint answer: `one-envelope`).

The property under test: a suggestion round's cost enters the SAME opening grant
envelope as the enrichment cost, priced as a worst-case ceiling, folded into the
projected execution count BEFORE the ceiling verdict runs, and refused before it starts
with Phase 57's existing `CEILING_OVER` split offer -- with the omitted-args path staying
byte-identical to the pre-Phase-62 envelope for every existing caller.
"""
import pytest

import config_gate
import executions_client
import write_grant

WORKFLOW_ID = "wf-enrichment-1"


@pytest.fixture(autouse=True)
def _clear_workflow_id_cache():
    """`executions_client._workflow_id_cache` is process-lifetime (test_write_grant.py's
    own fixture, mirrored here) -- without this a resolved id leaks between tests in
    this file and a scripted transport's response ordering silently shifts."""
    executions_client._workflow_id_cache.clear()
    yield
    executions_client._workflow_id_cache.clear()


def _base_workflow(record_writes='"false"', create='"false"'):
    gate = (f"const ALLOW_HUBSPOT_RECORD_WRITES = {record_writes};\n"
            f"const ALLOW_HUBSPOT_CREATE = {create};\n"
            "const ALLOW_HUBSPOT_REVIEW_WRITES = \"false\";\n"
            "const TEST_RECORD_IDS = \"\";\n"
            "const TEST_RECORD_DOMAINS = \"\";\n"
            "function _writeSafetyAllows() { return false; }\n")
    return {
        "id": WORKFLOW_ID,
        "name": write_grant.LANES["enrichment"],
        "active": True,
        "settings": {},
        "connections": {},
        "nodes": [
            {"name": "Update Write Gate", "parameters": {"jsCode": gate}},
            {"name": "Create Write Gate", "parameters": {"jsCode": gate}},
            {"name": "Webhook", "parameters": {}},
        ],
    }


def _workflow_list():
    return {"data": [{"id": WORKFLOW_ID, "name": write_grant.LANES["enrichment"]}]}


def _executions_page():
    """One exhausted, empty page -- `sampled: True`, `spent_sampled: 0`."""
    return {"data": []}


def _priced_config(**overrides):
    return {
        "n8n_url": "https://fake-tenant.n8n.cloud",
        "webhook_secret": "fake-secret-for-tests-only",
        "n8n_api_key": "fake-n8n-api-key-for-tests-only",
        config_gate.WRITE_GRANT_SETTINGS_KEY: True,
        "n8n_monthly_execution_allowance": 2500,
        "max_records_per_chunk": 5,
        **overrides,
    }


HEADROOM = {
    "allowance": 2500, "spent_sampled": 0, "remaining_sampled": 2500,
    "sampled": True, "covers_full_window": True, "listing_exhausted": True,
    "truncated_by_page_cap": False,
}


def _envelope(config, **kwargs):
    """`envelope()` needs no transport at all when `headroom=` and an empty provider
    list are both supplied directly -- no balances POST, no executions-list GET."""
    return write_grant.envelope(
        config, object_type="companies", record_ids=["1"], record_domains=[],
        providers=[], headroom=HEADROOM, **kwargs)


# ============================================================================
# envelope(): the omitted-args path stays byte-identical
# ============================================================================


def test_omitting_both_suggestion_args_leaves_figures_identical_to_the_pre_phase_62_call():
    config = _priced_config()
    before = _envelope(config)
    after = _envelope(config, suggestion_companies=None, suggestion_cap=None)

    assert before == after
    assert after["suggestion_allowance"] is None
    assert "suggestion_allowance" not in after["basis"]
    assert "suggestion" not in after["block"].lower()
    assert "Suggestion round" not in after["block"]


def test_omitting_the_args_does_not_widen_projected_executions():
    config = _priced_config()
    without = _envelope(config)
    assert without["projected_executions"] == 1 + 1  # 1 chunk + 1 record


# ============================================================================
# envelope(): a priced suggestion round
# ============================================================================


def test_a_priced_suggestion_round_is_a_third_figures_key_never_colliding_with_ceiling():
    config = _priced_config()
    figures = _envelope(config, suggestion_companies=4, suggestion_cap=3)

    assert figures["suggestion_allowance"] is not None
    assert type(figures["chunk_ceiling"]) is int
    assert type(figures["ceiling"]) is dict
    assert figures["basis"]["suggestion_allowance"] == write_grant.PROJECTED


def test_record_count_is_unchanged_by_a_suggestion_allowance():
    config = _priced_config()
    without = _envelope(config)
    with_suggestion = _envelope(config, suggestion_companies=4, suggestion_cap=3)

    assert with_suggestion["record_count"] == without["record_count"] == 1


def test_projected_executions_with_a_suggestion_allowance_is_strictly_greater():
    config = _priced_config()
    without = _envelope(config)
    with_suggestion = _envelope(config, suggestion_companies=4, suggestion_cap=3)

    assert with_suggestion["projected_executions"] > without["projected_executions"]


def test_priced_cap_defaults_to_3_the_top_of_the_2_to_3_band_when_no_cap_supplied():
    config = _priced_config()
    figures = _envelope(config, suggestion_companies=5)
    assert figures["suggestion_allowance"]["priced_cap"] == 3
    assert write_grant.PRICED_CAP == 3


def test_priced_cap_honours_an_explicit_cap():
    config = _priced_config()
    figures = _envelope(config, suggestion_companies=5, suggestion_cap=2)
    assert figures["suggestion_allowance"]["priced_cap"] == 2


def test_zero_suggestion_companies_prices_a_no_rows_allowance_and_widens_nothing():
    config = _priced_config()
    without = _envelope(config)
    with_zero = _envelope(config, suggestion_companies=0, suggestion_cap=3)

    assert with_zero["suggestion_allowance"]["state"] == "no_rows"
    assert with_zero["projected_executions"] == without["projected_executions"]


def test_the_rendered_block_carries_the_worst_case_disclosure_and_both_ceiling_components():
    config = _priced_config()
    figures = _envelope(config, suggestion_companies=4, suggestion_cap=3)
    block = figures["block"]

    assert "worst case" in block.lower()
    assert "unspent allowance is simply not spent" in block.lower()
    assert "fetch" in block.lower()
    assert "credit" in block.lower()


# ============================================================================
# plan_grant(): the ceiling verdict sees the suggestion weight (D-62-13)
# ============================================================================


def test_plan_grant_refuses_over_ceiling_when_only_the_suggestion_weight_pushes_it_over(
        stub_module_transport_factory):
    """A batch that fits WITHOUT the allowance (1 record -> 2 projected executions,
    allowance 5) is refused WITH it (5 companies x cap 3 = 15 contacts -> a large
    stage-2 projection), and the refusal carries Phase 57's existing split offer."""
    config = _priced_config(n8n_monthly_execution_allowance=5)
    transport = stub_module_transport_factory([_workflow_list(), _executions_page()])

    fits_without = write_grant.plan_grant(
        config, lanes=["enrichment"], object_type="companies", record_ids=["1"],
        record_domains=[], allow_create=False, label="no-suggestion probe",
        transport=stub_module_transport_factory(
            [_workflow_list(), _executions_page(), _base_workflow()]))
    assert fits_without["kind"] == write_grant.PROPOSAL_KIND, fits_without

    result = write_grant.plan_grant(
        config, lanes=["enrichment"], object_type="companies", record_ids=["1"],
        record_domains=[], allow_create=False, label="suggestion-heavy batch",
        transport=transport,
        suggestion_companies=5, suggestion_cap=3)

    assert result["outcome"] == write_grant.REFUSED
    assert result["ceiling"]["verdict"] == write_grant.CEILING_OVER
    assert "split_offer" in result
    assert result["split_offer"]["affordable_spec"] is not None
    assert transport.mutating_calls == []


def test_plan_grant_with_no_suggestion_args_is_unaffected_by_the_new_kwargs(
        stub_module_transport_factory):
    """Passing neither `suggestion_companies` nor `suggestion_cap` to `plan_grant`
    reaches `envelope()` with both `None`, the byte-identical path."""
    config = _priced_config()
    transport = stub_module_transport_factory(
        [_workflow_list(), _executions_page(), _base_workflow()])

    result = write_grant.plan_grant(
        config, lanes=["enrichment"], object_type="companies", record_ids=["1"],
        record_domains=[], allow_create=False, label="no suggestion at all",
        transport=transport)

    assert result["kind"] == write_grant.PROPOSAL_KIND, result
    assert result["envelope"]["suggestion_allowance"] is None
