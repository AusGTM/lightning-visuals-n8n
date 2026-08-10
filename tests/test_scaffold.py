"""Phase 1 scaffold proof: configs load, schemas validate, fixtures parse.

Runnable proof for SC1 (5 configs), SC2 (6 schemas), SC3 (5 fixtures).
Plain pytest asserts, no fixture framework. Paths resolve from the repo root
so the test passes regardless of pytest invocation cwd.
"""
import glob
import json
from pathlib import Path

import pytest
import yaml

from src.schemas import (
    CandidateValue,
    FieldDecision,
    HubSpotRecord,
    ICPScoreResult,
    MergeResult,
    ProviderEvidence,
    ProviderResult,
)

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
FIXTURE_DIR = ROOT / "tests" / "fixtures"

PROVIDER_FIXTURES = [
    "provider_apollo_company.json",
    "provider_zoominfo_company.json",
    "provider_lusha_company.json",
    "claude_web_research_company.json",
]


def load_json(name):
    return json.loads((FIXTURE_DIR / name).read_text())


def test_configs_load():
    """SC1: exactly 9 config YAMLs load; icp_scoring version is lv-icp-v0.1."""
    files = sorted(glob.glob(str(CONFIG_DIR / "*.yaml")))
    # +column_mapping.yaml (Phase 6), +taxonomy.yaml (Phase 12), +hubspot_properties.yaml
    # (Phase 15), +execution_budget.yaml (Phase 44 Plan 02, D-11)
    assert len(files) == 9, files
    cfg = {Path(f).name: yaml.safe_load(open(f)) for f in files}
    assert cfg["icp_scoring.yaml"]["version"] == "lv-icp-v0.1"
    assert cfg["taxonomy.yaml"]["version"] == "lv-taxonomy-v1"
    assert set(cfg["provider_priority.yaml"]) >= {"companies", "contacts"}
    assert "aliases" in cfg["column_mapping.yaml"]


def test_hubspot_record_fixture():
    """SC2/SC3: company_current.json validates as HubSpotRecord."""
    record = HubSpotRecord(**load_json("company_current.json"))
    assert record.object_type == "companies"
    assert record.id == "789"


@pytest.mark.parametrize("fixture", PROVIDER_FIXTURES)
def test_provider_result_fixtures(fixture):
    """SC2/SC3: each provider/research fixture validates as ProviderResult."""
    result = ProviderResult(**load_json(fixture))
    assert result.object_type == "companies"


def test_remaining_schemas_validate():
    """SC2: the other schema classes instantiate under pydantic v2."""
    apollo = load_json("provider_apollo_company.json")
    evidence = ProviderEvidence(**apollo["evidence"])

    candidate = CandidateValue(
        canonical_field="annualrevenue",
        provider="apollo",
        value=12000000,
        normalized_value="5-50M",
        confidence=74,
        evidence=evidence,
    )

    field_decision = FieldDecision(
        field="annualrevenue",
        current_value="",
        decision="stage_only",
        reason="scaffold test",
    )

    icp_score = ICPScoreResult(
        score=80,
        tier="A",
        anti_icp_flag=False,
        recommended_motion="work_direct",
        confidence=85,
        breakdown={},
        scoring_version="lv-icp-v0.1",
    )

    merge = MergeResult(
        object_type="companies",
        record_id="789",
        run_id="scaffold",
        field_decisions=[field_decision],
        staging_patch={},
        canonical_patch={},
        metadata_patch={},
        status_patch={},
        full_patch={},
    )

    assert candidate.provider == "apollo"
    assert icp_score.tier == "A"
    assert merge.field_decisions[0].decision == "stage_only"
