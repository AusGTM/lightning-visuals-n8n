"""tests/test_remediate_veto_companies.py

Phase 47 Plan 01 -- offline tests for scripts/remediate_veto_companies.py. No network
calls anywhere in this module -- every test either monkeypatches requests.get/post to
raise, injects a fake get_record, or exercises pure functions.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

import scripts.remediate_veto_companies as m  # noqa: E402

PINNED_ID = "9604732797"  # Tweed Valley Jockey Club

_FAKE_RECORD_PROPS = {
    "name": "Tweed Valley Jockey Club",
    "domain": "tvjc.example",
    "website": "https://tvjc.example",
    "country": "Australia",
    "industry": "Sports",
}


def _fake_get_record(object_type, record_id, properties):
    return {"id": record_id, "properties": dict(_FAKE_RECORD_PROPS)}


def _refuse_network(*_a, **_kw):
    raise AssertionError("no network call should be made in this test")


def _arm_credentials_and_env(monkeypatch, *, dry_run_unset=True):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", m.EXPECTED_PORTAL_ID)
    monkeypatch.setenv("USE_MOCK_WEB_RESEARCH", "true")
    if dry_run_unset:
        monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("ALLOW_VETO_REMEDIATION", raising=False)
    monkeypatch.delenv("VETO_MAX_RECORDS", raising=False)
    monkeypatch.setattr(m, "get_record", _fake_get_record)
    monkeypatch.setattr("requests.post", _refuse_network)
    monkeypatch.setattr("requests.get", _refuse_network)


# --- Task 1: tracer -----------------------------------------------------------------------

def test_tracer_single_pinned_company_disarmed_prints_all_payloads_no_network(monkeypatch, capsys):
    _arm_credentials_and_env(monkeypatch)

    exit_code = m.main(["--company-id", PINNED_ID])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "lv_country_region_normalized" in out
    assert "org_type_score" in out
    assert "lv_org_type_validation_status" in out
    assert "objectId" in out
    assert PINNED_ID in out


def test_pinned_id_order_and_disjoint_from_excluded():
    assert len(m.PINNED_COMPANY_ID_ORDER) == 17
    assert len(m.PINNED_COMPANY_IDS) == 17
    assert m.PINNED_COMPANY_IDS.isdisjoint(m.EXCLUDED_COMPANY_IDS)


def test_resolved_max_records_default_is_17(monkeypatch):
    monkeypatch.delenv("VETO_MAX_RECORDS", raising=False)
    assert m._resolved_max_records() == 17


def test_main_with_no_flags_resolves_to_all_17_in_pinned_order(monkeypatch, capsys):
    _arm_credentials_and_env(monkeypatch)

    exit_code = m.main([])

    assert exit_code == 0
    out = capsys.readouterr().out
    for line in out.splitlines():
        if line.startswith("RESOLVED_IDS:"):
            import json
            resolved = json.loads(line[len("RESOLVED_IDS:"):].strip())
            assert tuple(resolved) == m.PINNED_COMPANY_ID_ORDER
            break
    else:
        raise AssertionError("no RESOLVED_IDS line printed")


def test_module_never_calls_search_records():
    source = (ROOT / "scripts" / "remediate_veto_companies.py").read_text()
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "search_records" not in names
    assert "search_records" not in attrs
