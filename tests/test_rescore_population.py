"""tests/test_rescore_population.py

Phase 49 Plan 01 -- offline tests for scripts/rescore_population.py. No network calls
anywhere in this module -- every test either monkeypatches the module's own
search_records/get_record/batch_update_companies names (imported by `from`, so patched on
the module namespace, same idiom as tests/test_remediate_veto_companies.py) or
requests.post/get to raise, or exercises pure functions.
"""
import sys
from pathlib import Path

import pytest

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


def _fake_get_record_factory(props_by_id):
    def _fake_get_record(object_type, record_id, properties):
        assert object_type == "companies"
        base = props_by_id.get(record_id, {})
        return {"id": record_id, "properties": {k: base.get(k) for k in properties}}
    return _fake_get_record


def _arm_credentials_and_env(monkeypatch, *, ids=None, armed=False, props_by_id=None):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", rp.EXPECTED_PORTAL_ID)
    if armed:
        monkeypatch.setenv("DRY_RUN", "false")
        monkeypatch.setenv("ALLOW_SCORE_BACKFILL", "true")
    else:
        monkeypatch.delenv("DRY_RUN", raising=False)
        monkeypatch.delenv("ALLOW_SCORE_BACKFILL", raising=False)
    # Always monkeypatch this one (even if unset) so pytest's monkeypatch fixture
    # cleans up whatever _apply_max_records_default()'s os.environ.setdefault leaves
    # behind at teardown -- see build_plan()'s docstring / the module's own comment.
    monkeypatch.delenv("BACKFILL_MAX_RECORDS", raising=False)
    monkeypatch.setattr("requests.post", _refuse_network)
    monkeypatch.setattr("requests.get", _refuse_network)
    monkeypatch.setattr(rp.time, "sleep", lambda _s: None)  # settle-poll never really sleeps in tests
    if ids is not None:
        monkeypatch.setattr(rp, "search_records", _fake_search_records_factory(ids))
    if props_by_id is not None:
        monkeypatch.setattr(rp, "get_record", _fake_get_record_factory(props_by_id))


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


def test_select_scored_population_refuses_a_truncated_page(monkeypatch):
    """A page limit alone does not prevent truncation -- it only relocates it. Both reads
    of the exact-set gate call this function, so a truncated page would let the gate agree
    with itself on a subset. Refuse on any shortfall against the reported total."""
    def _fake(object_type, filters, properties, limit=100):
        return {"total": 140, "results": [{"id": str(i)} for i in range(limit)]}

    monkeypatch.setattr(rp, "search_records", _fake)
    with pytest.raises(RuntimeError, match="REFUSED"):
        rp.select_scored_population()


def test_select_scored_population_accepts_a_complete_page(monkeypatch):
    """The guard must not fire when the page holds the whole population -- the live case."""
    def _fake(object_type, filters, properties, limit=100):
        return {"total": 3, "results": [{"id": "2"}, {"id": "1"}, {"id": "3"}]}

    monkeypatch.setattr(rp, "search_records", _fake)
    assert rp.select_scored_population() == ["1", "2", "3"]


def test_select_scored_population_tolerates_a_missing_total(monkeypatch):
    """Some search stubs omit `total`; absence must not be read as a shortfall."""
    monkeypatch.setattr(rp, "search_records", _fake_search_records_factory(["1", "2"]))
    assert rp.select_scored_population() == ["1", "2"]


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


# --- CLI: --execute (Task 49-01-02) --------------------------------------------------------

def test_execute_disarmed_no_arm_vars_builds_prints_no_write(monkeypatch, capsys):
    _arm_credentials_and_env(monkeypatch, ids=STUB_66_IDS, props_by_id={})
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    exit_code = rp.main(["--execute"])
    assert exit_code == 0
    assert batch_calls == []


def test_execute_dry_run_false_but_allow_unset_zero_writes(monkeypatch):
    _arm_credentials_and_env(monkeypatch, ids=STUB_66_IDS, props_by_id={})
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.delenv("ALLOW_SCORE_BACKFILL", raising=False)
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    exit_code = rp.main(["--execute"])
    assert exit_code == 0
    assert batch_calls == []


def test_execute_armed_population_drift_refuses_and_makes_no_write(monkeypatch):
    calls = {"n": 0}
    ids_first = STUB_66_IDS
    ids_second = STUB_66_IDS[:-1] + ["99999"]  # one id different -- simulates a race

    def _fake_search(object_type, filters, properties, limit=100):
        calls["n"] += 1
        return {"results": [{"id": i} for i in (ids_first if calls["n"] == 1 else ids_second)]}

    _arm_credentials_and_env(monkeypatch, armed=True, props_by_id={})
    monkeypatch.setattr(rp, "search_records", _fake_search)
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    exit_code = rp.main(["--execute"])
    assert exit_code != 0
    assert batch_calls == []


def test_execute_armed_matching_sample_writes_all(monkeypatch):
    ids = ["00010", "00020", "00030"]
    _arm_credentials_and_env(monkeypatch, ids=ids, armed=True, props_by_id={})
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    exit_code = rp.main(["--execute"])
    assert exit_code == 0
    assert len(batch_calls) == 1
    sent_ids = sorted(u["id"] for u in batch_calls[0])
    assert sent_ids == ids


def test_execute_already_written_excludes_canary_sends_65(monkeypatch):
    ids = STUB_66_IDS
    canary_id = ids[0]
    _arm_credentials_and_env(monkeypatch, ids=ids, armed=True, props_by_id={})
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    exit_code = rp.main(["--execute", "--already-written", canary_id])
    assert exit_code == 0
    assert len(batch_calls) == 1
    sent_ids = [u["id"] for u in batch_calls[0]]
    assert len(sent_ids) == 65
    assert canary_id not in sent_ids


def test_execute_payload_component_keys_are_exact(monkeypatch):
    ids = ["00010", "00020"]
    _arm_credentials_and_env(monkeypatch, ids=ids, armed=True, props_by_id={})
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    rp.main(["--execute"])
    assert len(batch_calls) == 1
    for update in batch_calls[0]:
        assert set(update["properties"].keys()) == set(rp.COMPONENT_PROPS)


# --- CLI: --canary (Task 49-01-02) ----------------------------------------------------------

def test_canary_armed_writes_exactly_one_record(monkeypatch):
    ids = ["00010", "00020"]
    props_by_id = {
        "00010": {"lv_org_type": "individual_club_team"},
        "00020": {"lv_org_type": "governing_body_league"},
    }
    _arm_credentials_and_env(monkeypatch, ids=ids, armed=True, props_by_id=props_by_id)
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    exit_code = rp.main(["--canary"])
    assert exit_code == 0
    assert len(batch_calls) == 1
    assert len(batch_calls[0]) == 1


def test_canary_selects_lower_sorted_individual_club_team_id(monkeypatch):
    ids = ["00010", "00020", "00030"]
    props_by_id = {
        "00010": {"lv_org_type": "governing_body_league"},
        "00020": {"lv_org_type": "individual_club_team"},
        "00030": {"lv_org_type": "individual_club_team"},
    }
    _arm_credentials_and_env(monkeypatch, ids=ids, armed=True, props_by_id=props_by_id)
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    rp.main(["--canary"])
    assert batch_calls[0][0]["id"] == "00020"


def test_canary_selection_changes_when_stub_ids_change(monkeypatch):
    # Proves selection is by rule (lower sorted individual_club_team id), not a literal:
    # relabeling which id carries individual_club_team changes the chosen canary.
    ids = ["00010", "00020", "00030"]
    props_by_id = {
        "00010": {"lv_org_type": "individual_club_team"},
        "00020": {"lv_org_type": "governing_body_league"},
        "00030": {"lv_org_type": "governing_body_league"},
    }
    _arm_credentials_and_env(monkeypatch, ids=ids, armed=True, props_by_id=props_by_id)
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    rp.main(["--canary"])
    assert batch_calls[0][0]["id"] == "00010"


def test_canary_fallback_when_no_individual_club_team_record(monkeypatch):
    # No individual_club_team record -- falls back to the first id whose freshly
    # computed components differ from what is currently stored.
    ids = ["00010", "00020"]
    props_by_id = {
        # already has the CORRECT stored components for governing_body_league (40) --
        # computed == stored, so this record should be skipped by the fallback.
        "00010": {"lv_org_type": "governing_body_league", "org_type_score": 40,
                  "geography_score": 0, "annual_revenue_score": 0,
                  "produces_content_score": 0, "gambling_score": 0},
        # stale stored components (0) that no longer match a fresh compute (20) --
        # this is the one the fallback should pick.
        "00020": {"lv_org_type": "content_producer", "org_type_score": 0,
                  "geography_score": 0, "annual_revenue_score": 0,
                  "produces_content_score": 0, "gambling_score": 0},
    }
    _arm_credentials_and_env(monkeypatch, ids=ids, armed=True, props_by_id=props_by_id)
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    rp.main(["--canary"])
    assert batch_calls[0][0]["id"] == "00020"


# --- settle_population -----------------------------------------------------------------------

def test_settle_population_default_timeout_is_300():
    import inspect
    sig = inspect.signature(rp.settle_population)
    assert sig.parameters["timeout"].default == 300


def test_settle_population_polls_get_record_until_stable(monkeypatch):
    reads = {"n": 0}
    values = ["A", "A"]  # already stable on first read pair

    def _fake_get_record(object_type, record_id, properties):
        idx = min(reads["n"], len(values) - 1)
        reads["n"] += 1
        return {"id": record_id, "properties": {properties[0]: values[idx]}}

    monkeypatch.setattr(rp, "get_record", _fake_get_record)
    monkeypatch.setattr(rp.time, "sleep", lambda _s: None)
    result = rp.settle_population(["1"], "lv_icp_tier", timeout=300, interval=1)
    assert result == {"1": "A"}


# --- CLI: --snapshot (Task 49-01-03) --------------------------------------------------------

def _snapshot_props_by_id(ids):
    props = {}
    for idx, company_id in enumerate(ids):
        tier = ["A", "B", "C", "D", "Unscored", "Needs Review"][idx % 6]
        props[company_id] = {
            "name": f"Company {company_id}",
            "lv_icp_tier": tier,
            "lv_icp_fit_score": str(idx),
            "lv_org_type": "governing_body_league",
            "lv_anti_icp_flag": "false",
            "lv_anti_icp_reason": None,
        }
    return props


def test_snapshot_population_count_and_tier_sum(monkeypatch, capsys):
    ids = STUB_66_IDS
    _arm_credentials_and_env(monkeypatch, ids=ids, props_by_id=_snapshot_props_by_id(ids))
    exit_code = rp.main(["--snapshot"])
    assert exit_code == 0
    import json
    printed = json.loads(capsys.readouterr().out)
    assert printed["population_count"] == 66
    assert sum(printed["tier_distribution"].values()) == 66


def test_snapshot_records_sorted_by_id_with_seven_keys(monkeypatch, capsys):
    ids = STUB_66_IDS
    _arm_credentials_and_env(monkeypatch, ids=ids, props_by_id=_snapshot_props_by_id(ids))
    rp.main(["--snapshot"])
    import json
    printed = json.loads(capsys.readouterr().out)
    record_ids = [r["id"] for r in printed["records"]]
    assert record_ids == sorted(record_ids)
    for record in printed["records"]:
        assert set(record.keys()) == {
            "id", "name", "lv_icp_tier", "lv_icp_fit_score", "lv_org_type",
            "lv_anti_icp_flag", "lv_anti_icp_reason",
        }


def test_snapshot_byte_identical_across_two_runs_except_derived_at(monkeypatch, capsys):
    ids = ["00010", "00020", "00030"]
    _arm_credentials_and_env(monkeypatch, ids=ids, props_by_id=_snapshot_props_by_id(ids))
    rp.main(["--snapshot"])
    first = capsys.readouterr().out
    rp.main(["--snapshot"])
    second = capsys.readouterr().out

    import json

    def _strip_derived_at(text):
        parsed = json.loads(text)
        assert "derived_at" in parsed
        parsed.pop("derived_at")
        return json.dumps(parsed, indent=2, sort_keys=False)

    assert _strip_derived_at(first) == _strip_derived_at(second)


def test_snapshot_makes_zero_writes_even_when_armed(monkeypatch, capsys):
    ids = STUB_66_IDS
    _arm_credentials_and_env(monkeypatch, ids=ids, armed=True, props_by_id=_snapshot_props_by_id(ids))
    batch_calls = []
    monkeypatch.setattr(rp, "batch_update_companies", lambda updates, dry_run=True: batch_calls.append(updates))
    exit_code = rp.main(["--snapshot"])
    assert exit_code == 0
    assert batch_calls == []


def test_snapshot_empty_population_refuses(monkeypatch, capsys):
    _arm_credentials_and_env(monkeypatch, ids=[], props_by_id={})
    exit_code = rp.main(["--snapshot"])
    assert exit_code != 0
    out = capsys.readouterr().out
    assert "REFUSED" in out
    assert "population_count" not in out


def test_snapshot_none_tier_counted_as_distinct_key_not_dropped(monkeypatch, capsys):
    ids = ["00010", "00020"]
    props_by_id = {
        "00010": {"name": "A", "lv_icp_tier": None, "lv_icp_fit_score": None,
                  "lv_org_type": None, "lv_anti_icp_flag": None, "lv_anti_icp_reason": None},
        "00020": {"name": "B", "lv_icp_tier": "A", "lv_icp_fit_score": "80",
                  "lv_org_type": "governing_body_league", "lv_anti_icp_flag": "false",
                  "lv_anti_icp_reason": None},
    }
    _arm_credentials_and_env(monkeypatch, ids=ids, props_by_id=props_by_id)
    rp.main(["--snapshot"])
    import json
    printed = json.loads(capsys.readouterr().out)
    assert sum(printed["tier_distribution"].values()) == 2
    assert "Unscored-or-blank" in printed["tier_distribution"]
    assert printed["tier_distribution"]["Unscored-or-blank"] == 1


def test_snapshot_out_flag_writes_file(monkeypatch, tmp_path):
    ids = ["00010"]
    _arm_credentials_and_env(monkeypatch, ids=ids, props_by_id=_snapshot_props_by_id(ids))
    out_file = tmp_path / "snapshot.json"
    exit_code = rp.main(["--snapshot", "--out", str(out_file)])
    assert exit_code == 0
    import json
    written = json.loads(out_file.read_text())
    assert written["population_count"] == 1


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
