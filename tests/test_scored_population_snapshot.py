# tests/test_scored_population_snapshot.py
#
# Phase 51 Plan 03 -- offline, mocked tests for scripts/scored_population_snapshot.py.
# Plain pytest, plain asserts, no classes/fixtures beyond plain helper functions (matches
# tests/test_icp_scoring.py's style). No live HubSpot call happens in this suite -- every
# network-touching function is monkeypatched.
from pathlib import Path

import pytest

import scripts.rescore_population as rescore_population
from scripts import scored_population_snapshot as snap


def test_snapshot_shape_and_ordering(monkeypatch):
    ids = ["300", "100", "200"]
    monkeypatch.setattr(snap, "select_scored_population", lambda: ids)

    def mock_get_record(object_type, record_id, properties):
        assert object_type == "companies"
        return {"properties": {name: f"{record_id}-{name}" for name in properties}}

    monkeypatch.setattr(snap, "get_record", mock_get_record)

    result = snap.capture_snapshot()

    assert result["population_definition"] == "HAS_PROPERTY(lv_icp_fit_score)"
    assert result["population_count"] == 3
    assert [r["id"] for r in result["records"]] == ["100", "200", "300"]
    for record in result["records"]:
        assert set(record["properties"].keys()) == set(snap.SNAPSHOT_PROPS)
        for name in snap.SNAPSHOT_PROPS:
            assert record["properties"][name] == f"{record['id']}-{name}"


def test_snapshot_refuses_truncated_population(monkeypatch, tmp_path):
    def mock_search_records(object_type, filters, properties, limit=100):
        return {"total": 5, "results": [{"id": "1", "properties": {"lv_icp_fit_score": "80"}}]}

    monkeypatch.setattr(rescore_population, "search_records", mock_search_records)

    out_path = tmp_path / "snapshot.json"
    with pytest.raises(RuntimeError, match="page limit"):
        snap.capture_snapshot()

    assert not out_path.exists()


def test_snapshot_uses_shared_population_definition():
    assert snap.select_scored_population is rescore_population.select_scored_population


def test_snapshot_is_read_only():
    source = Path(snap.__file__).read_text()
    for forbidden in ("patch_record", "batch_update_companies", "create_record"):
        assert forbidden not in source
