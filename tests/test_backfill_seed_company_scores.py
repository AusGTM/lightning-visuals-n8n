"""tests/test_backfill_seed_company_scores.py

Phase 40 Plan 07 (D-10) — offline tests for:
  - src/hubspot_client.batch_update_companies() (Task 1)
  - scripts/backfill_seed_company_scores.py's component computation and gates (Task 2)

No network calls anywhere in this module — every test either monkeypatches
requests.post to raise, or exercises pure functions.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

from src.hubspot_client import batch_update_companies  # noqa: E402


# --- Task 1: batch_update_companies -----------------------------------------------------

def test_batch_update_dry_run_default_makes_no_network_call(monkeypatch, capsys):
    def _fail(*a, **kw):
        raise AssertionError("no HTTP call should be made in dry-run")

    monkeypatch.setattr("requests.post", _fail)
    updates = [{"id": "789", "properties": {"org_type_score": 40}}]
    result = batch_update_companies(updates)  # dry_run defaults to True
    assert result == {"dry_run": True, "payload": {"inputs": updates}}
    out = capsys.readouterr().out
    assert "Authorization" not in out
    assert "Bearer" not in out


def test_batch_update_dry_run_explicit_true_matches_default(monkeypatch):
    def _fail(*a, **kw):
        raise AssertionError("no HTTP call should be made in dry-run")

    monkeypatch.setattr("requests.post", _fail)
    updates = [{"id": "789", "properties": {"org_type_score": 40}}]
    result = batch_update_companies(updates, dry_run=True)
    assert result == {"dry_run": True, "payload": {"inputs": updates}}


def test_batch_update_payload_envelope_is_inputs_key(monkeypatch, capsys):
    monkeypatch.setattr("requests.post", lambda *a, **kw: (_ for _ in ()).throw(AssertionError()))
    updates = [
        {"id": "1", "properties": {"org_type_score": 40}},
        {"id": "2", "properties": {"org_type_score": 5}},
    ]
    result = batch_update_companies(updates, dry_run=True)
    assert result["payload"] == {"inputs": updates}
    assert list(result["payload"].keys()) == ["inputs"]


def test_batch_update_over_100_entries_raises_and_makes_no_network_call(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **kw: (_ for _ in ()).throw(AssertionError()))
    updates = [{"id": str(i), "properties": {"org_type_score": 0}} for i in range(101)]
    try:
        batch_update_companies(updates, dry_run=True)
        raise AssertionError("expected batch_update_companies to raise for a 101-entry list")
    except ValueError:
        pass


def test_batch_update_empty_list_short_circuits_dry_run(monkeypatch):
    monkeypatch.setattr("requests.post", lambda *a, **kw: (_ for _ in ()).throw(AssertionError()))
    result = batch_update_companies([], dry_run=True)
    assert result == {"dry_run": True, "payload": {"inputs": []}}


def test_batch_update_empty_list_short_circuits_live_mode_too(monkeypatch):
    # An empty updates list must never hit the network even with dry_run=False —
    # there is nothing to send.
    monkeypatch.setattr("requests.post", lambda *a, **kw: (_ for _ in ()).throw(AssertionError()))
    result = batch_update_companies([], dry_run=False)
    assert result == {"dry_run": True, "payload": {"inputs": []}}


def test_batch_update_live_calls_requests_post_with_expected_shape(monkeypatch):
    calls = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"status": "COMPLETE"}

    def _fake_post(url, headers=None, json=None, timeout=None):
        calls["url"] = url
        calls["headers"] = headers
        calls["json"] = json
        calls["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("requests.post", _fake_post)
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")

    updates = [{"id": "789", "properties": {"org_type_score": 40}}]
    result = batch_update_companies(updates, dry_run=False)
    assert calls["url"] == "https://api.hubapi.com/crm/v3/objects/companies/batch/update"
    assert calls["json"] == {"inputs": updates}
    assert calls["headers"]["Authorization"] == "Bearer fake-token"
    assert result == {"status": "COMPLETE"}


# --- Task 2: backfill component computation and gates -----------------------------------
# These import scripts.backfill_seed_company_scores, which does not exist until Task 2
# lands. Deferred imports (inside each test) so Task 1's RED->GREEN cycle for
# batch_update_companies is not blocked by a ModuleNotFoundError from Task 2's script.

def _import_backfill():
    import scripts.backfill_seed_company_scores as backfill
    return backfill


def test_backfill_component_scores_org_type_sweep():
    backfill = _import_backfill()
    import yaml
    cfg = yaml.safe_load(open("config/icp_scoring.yaml"))
    for org_type, points in cfg["base_score"]["org_type"].items():
        components = backfill.compute_components({"lv_org_type": org_type})
        assert components["org_type_score"] == points


def test_backfill_component_scores_produces_content_both_values():
    backfill = _import_backfill()
    assert backfill.compute_components({"lv_produces_content": "true"})["produces_content_score"] == 20
    assert backfill.compute_components({"lv_produces_content": "false"})["produces_content_score"] == 0


def test_backfill_component_scores_geography_all_four_region_cases():
    backfill = _import_backfill()
    assert backfill.compute_components({"lv_country_region_normalized": "AU"})["geography_score"] == 10
    assert backfill.compute_components({"lv_country_region_normalized": "NZ"})["geography_score"] == 10
    assert backfill.compute_components({"lv_country_region_normalized": "ANZ"})["geography_score"] == 10
    assert backfill.compute_components({"lv_country_region_normalized": "US"})["geography_score"] == 0


def test_backfill_component_scores_revenue_all_nine_bands():
    backfill = _import_backfill()
    import yaml
    cfg = yaml.safe_load(open("config/icp_scoring.yaml"))
    for band, points in cfg["base_score"]["revenue_band"].items():
        components = backfill.compute_components({"lv_revenue_band": band})
        assert components["annual_revenue_score"] == points


def test_backfill_component_scores_gambling_deduction():
    backfill = _import_backfill()
    assert backfill.compute_components({"lv_is_gambling_operator": "true"})["gambling_score"] == -20
    assert backfill.compute_components({"lv_is_gambling_operator": "false"})["gambling_score"] == 0


def test_backfill_missing_inputs_produce_zero_for_every_component():
    backfill = _import_backfill()
    components = backfill.compute_components({})
    assert components == {
        "org_type_score": 0,
        "geography_score": 0,
        "annual_revenue_score": 0,
        "produces_content_score": 0,
        "gambling_score": 0,
    }


def test_backfill_never_writes_derived_output_properties():
    backfill = _import_backfill()
    components = backfill.compute_components({
        "lv_org_type": "governing_body_league",
        "lv_produces_content": "true",
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "50-500M",
        "lv_is_gambling_operator": "false",
    })
    for forbidden in ("lv_icp_fit_score", "lv_icp_tier", "lv_anti_icp_flag", "lv_anti_icp_reason"):
        assert forbidden not in components


def test_backfill_reads_points_from_loaded_config_not_a_second_table(monkeypatch):
    """Proves compute_components() reads through src/icp_scoring.py's loaded config --
    mutating a loaded point value changes the computed output."""
    backfill = _import_backfill()
    from src import icp_scoring
    import yaml
    base_cfg = yaml.safe_load(open("config/icp_scoring.yaml"))
    import copy
    mutated = copy.deepcopy(base_cfg)
    mutated["base_score"]["org_type"]["governing_body_league"] = 999
    monkeypatch.setattr(icp_scoring, "load_yaml", lambda _path, _cfg=mutated: _cfg)
    components = backfill.compute_components({"lv_org_type": "governing_body_league"})
    assert components["org_type_score"] == 999


def test_backfill_sample_cap_refuses_oversized_sample(monkeypatch):
    backfill = _import_backfill()
    monkeypatch.setenv("BACKFILL_MAX_RECORDS", "3")
    oversized = ["1", "2", "3", "4"]
    assert backfill.enforce_sample_cap(oversized) is False


def test_backfill_sample_cap_allows_sample_at_the_limit(monkeypatch):
    backfill = _import_backfill()
    monkeypatch.setenv("BACKFILL_MAX_RECORDS", "3")
    at_limit = ["1", "2", "3"]
    assert backfill.enforce_sample_cap(at_limit) is True


def test_backfill_refuses_to_write_without_both_arming_keys(monkeypatch):
    backfill = _import_backfill()
    monkeypatch.delenv("ALLOW_SCORE_BACKFILL", raising=False)
    monkeypatch.setenv("DRY_RUN", "false")
    assert backfill._writes_allowed() is False

    monkeypatch.setenv("ALLOW_SCORE_BACKFILL", "true")
    monkeypatch.setenv("DRY_RUN", "true")
    assert backfill._writes_allowed() is False

    monkeypatch.setenv("ALLOW_SCORE_BACKFILL", "true")
    monkeypatch.setenv("DRY_RUN", "false")
    assert backfill._writes_allowed() is True


def test_backfill_portal_guard_refuses_wrong_portal(monkeypatch):
    backfill = _import_backfill()
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "99999999")
    assert backfill._portal_ok() is False
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", backfill.EXPECTED_PORTAL_ID)
    assert backfill._portal_ok() is True


def test_backfill_build_updates_payload_never_contains_derived_fields():
    backfill = _import_backfill()
    records = [
        {"id": "1", "properties": {"lv_org_type": "governing_body_league", "lv_produces_content": "true",
                                    "lv_country_region_normalized": "AU", "lv_revenue_band": "50-500M",
                                    "lv_is_gambling_operator": "false"}},
        {"id": "2", "properties": {}},
    ]
    updates = backfill.build_updates(records)
    assert len(updates) == 2
    for update in updates:
        assert set(update["properties"].keys()) == {
            "org_type_score", "geography_score", "annual_revenue_score",
            "produces_content_score", "gambling_score",
        }
        for forbidden in ("lv_icp_fit_score", "lv_icp_tier", "lv_anti_icp_flag", "lv_anti_icp_reason"):
            assert forbidden not in update["properties"]
