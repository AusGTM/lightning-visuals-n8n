"""tests/test_rescore_population.py

Phase 49 Plan 01 -- offline tests for scripts/rescore_population.py. No network calls
anywhere in this module -- every test either monkeypatches the module's own
search_records/get_record/batch_update_companies names (imported by `from`, so patched on
the module namespace, same idiom as tests/test_remediate_veto_companies.py) or
requests.post/get to raise, or exercises pure functions.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

import scripts.rescore_population as rp  # noqa: E402

# A 66-id stub population, fixed-width so lexicographic (string) sort order matches
# numeric order -- avoids ordering surprises in tests that assert on `ids`.
STUB_66_IDS = [f"{i:05d}" for i in range(1, 67)]


def _refuse_network(*_a, **_kw):
    raise AssertionError("no network call should be made in this test")


def _fake_search_records_factory(ids):
    def _fake_search_records(object_type, filters, properties, limit=100):
        assert object_type == "companies"
        assert filters == [{"propertyName": "lv_icp_fit_score", "operator": "HAS_PROPERTY"}]
        return {"results": [{"id": i} for i in ids]}
    return _fake_search_records


def _arm_credentials_and_env(monkeypatch, *, ids=None):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", rp.EXPECTED_PORTAL_ID)
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("ALLOW_SCORE_BACKFILL", raising=False)
    # Always monkeypatch this one (even if unset) so pytest's monkeypatch fixture
    # cleans up whatever _apply_max_records_default()'s os.environ.setdefault leaves
    # behind at teardown -- see build_plan()'s docstring / the module's own comment.
    monkeypatch.delenv("BACKFILL_MAX_RECORDS", raising=False)
    monkeypatch.setattr("requests.post", _refuse_network)
    monkeypatch.setattr("requests.get", _refuse_network)
    if ids is not None:
        monkeypatch.setattr(rp, "search_records", _fake_search_records_factory(ids))


# --- select_scored_population ------------------------------------------------------------

def test_select_scored_population_returns_sorted_ids(monkeypatch):
    monkeypatch.setattr(rp, "search_records", _fake_search_records_factory(["3", "1", "2"]))
    assert rp.select_scored_population() == ["1", "2", "3"]


def test_select_scored_population_uses_limit_100(monkeypatch):
    seen = {}

    def _fake(object_type, filters, properties, limit=100):
        seen["limit"] = limit
        return {"results": []}

    monkeypatch.setattr(rp, "search_records", _fake)
    rp.select_scored_population()
    assert seen["limit"] == 100


# --- estimate_rescore_cost (RESCORE-01 precision truth) -----------------------------------

def test_estimate_rescore_cost_weight_branch_all_zero_except_batch_calls():
    cost = rp.estimate_rescore_cost(STUB_66_IDS, branch="weight")
    assert cost["n8n_executions"] == 0
    assert cost["anthropic_calls"] == 0
    assert cost["provider_credits"] == 0
    assert cost["hubspot_batch_calls"] == 1
    for key in ("n8n_executions", "anthropic_calls", "provider_credits", "hubspot_batch_calls", "records"):
        assert isinstance(cost[key], int), f"{key} must be an int, got {type(cost[key])}"


def test_estimate_rescore_cost_veto_branch_n8n_executions_equals_record_count():
    cost = rp.estimate_rescore_cost(STUB_66_IDS, branch="veto")
    assert cost["n8n_executions"] == 66
    assert cost["anthropic_calls"] == 0
    assert cost["provider_credits"] == 0


def test_estimate_rescore_cost_hubspot_batch_calls_is_integer_ceiling():
    over_one_chunk = [str(i) for i in range(150)]
    cost = rp.estimate_rescore_cost(over_one_chunk, branch="weight")
    assert cost["hubspot_batch_calls"] == 2
    assert isinstance(cost["hubspot_batch_calls"], int)


def test_estimate_rescore_cost_empty_population():
    cost = rp.estimate_rescore_cost([], branch="weight")
    assert cost["records"] == 0
    assert cost["hubspot_batch_calls"] == 0


# --- build_plan / --plan key contract (cross-plan contract, 49-02 parses these names) -----

def test_build_plan_top_level_key_set_is_exact(monkeypatch):
    monkeypatch.delenv("BACKFILL_MAX_RECORDS", raising=False)
    plan = rp.build_plan(STUB_66_IDS)
    assert set(plan.keys()) == {
        "ids", "population_count", "derived_at", "chunk_size", "chunks", "max_records",
        "window", "arm_keys", "arms_n8n_allowlist", "cost",
    }


def test_build_plan_values_for_66_id_population(monkeypatch):
    monkeypatch.delenv("BACKFILL_MAX_RECORDS", raising=False)
    plan = rp.build_plan(STUB_66_IDS)
    assert plan["population_count"] == 66
    assert plan["chunk_size"] == rp.BATCH_CHUNK_SIZE
    assert plan["chunks"] == 1
    assert plan["window"] == "W1"
    assert plan["arm_keys"] == ["DRY_RUN=false", "ALLOW_SCORE_BACKFILL=true"]
    assert plan["arms_n8n_allowlist"] is False
    assert plan["cost"]["hubspot_batch_calls"] == 1
    assert plan["max_records"] >= 66  # the 100-ceiling default must not refuse this population


# --- assert_payload_scope (T-49-02) -------------------------------------------------------

def test_assert_payload_scope_passes_for_build_updates_output():
    records = [{"id": "1", "properties": {"lv_org_type": "governing_body_league"}}]
    updates = rp.build_updates(records)
    rp.assert_payload_scope(updates)  # must not raise


def test_assert_payload_scope_raises_on_missing_component():
    bad = [{"id": "1", "properties": {
        "org_type_score": 10, "geography_score": 10, "annual_revenue_score": 0,
        "produces_content_score": 0,
        # gambling_score omitted
    }}]
    try:
        rp.assert_payload_scope(bad)
        raise AssertionError("expected ValueError for a missing component")
    except ValueError:
        pass


def test_assert_payload_scope_raises_on_sixth_key():
    bad = [{"id": "1", "properties": {
        "org_type_score": 10, "geography_score": 10, "annual_revenue_score": 0,
        "produces_content_score": 0, "gambling_score": 0,
        "lv_icp_fit_score": 40,  # forbidden sixth key
    }}]
    try:
        rp.assert_payload_scope(bad)
        raise AssertionError("expected ValueError for a sixth key")
    except ValueError:
        pass


# --- CLI: --plan mode ----------------------------------------------------------------------

def test_main_plan_mode_prints_plan_with_exact_key_set(monkeypatch, capsys):
    _arm_credentials_and_env(monkeypatch, ids=STUB_66_IDS)
    exit_code = rp.main(["--plan"])
    assert exit_code == 0
    out = capsys.readouterr().out
    import json
    printed = json.loads(out)
    assert set(printed.keys()) == {
        "ids", "population_count", "derived_at", "chunk_size", "chunks", "max_records",
        "window", "arm_keys", "arms_n8n_allowlist", "cost",
    }
    assert printed["population_count"] == 66


def test_main_default_mode_is_plan(monkeypatch, capsys):
    _arm_credentials_and_env(monkeypatch, ids=STUB_66_IDS)
    exit_code = rp.main([])
    assert exit_code == 0
    out = capsys.readouterr().out
    import json
    printed = json.loads(out)
    assert printed["population_count"] == 66


def test_main_plan_mode_makes_no_write_call(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda *a, **kw: calls.append((a, kw)))
    _arm_credentials_and_env(monkeypatch, ids=STUB_66_IDS)
    rp.main(["--plan"])
    assert calls == []


def test_main_plan_mode_refuses_on_wrong_portal(monkeypatch, capsys):
    _arm_credentials_and_env(monkeypatch, ids=STUB_66_IDS)
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "99999999")
    exit_code = rp.main(["--plan"])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "REFUSED" in out


def test_main_plan_mode_refuses_on_empty_population(monkeypatch, capsys):
    _arm_credentials_and_env(monkeypatch, ids=[])
    exit_code = rp.main(["--plan"])
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "REFUSED" in out
    # Never prints a plan document on the empty-population refusal path.
    assert "population_count" not in out


def test_main_skips_cleanly_with_no_credentials(monkeypatch, capsys):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.setattr("requests.post", _refuse_network)
    monkeypatch.setattr("requests.get", _refuse_network)
    exit_code = rp.main(["--plan"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "skipped" in out


# --- module hygiene ------------------------------------------------------------------------

def test_module_does_not_import_requests_directly():
    import ast
    source = Path(rp.__file__).read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "requests", "must go through src.hubspot_client, not requests directly"
        if isinstance(node, ast.ImportFrom):
            assert node.module != "requests"
