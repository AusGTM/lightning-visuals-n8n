"""tests/test_icp_scoring_generated_currency.py

Phase 75 Plan 01 Task 3 — pins n8n/code/icpScoring.generated.js to what
scripts/gen_icp_scoring_js.py would emit right now (mirrors tests/test_judge_spec.py's
test_escalation_generated_js_is_current and tests/test_hubspot_enums_generated_currency.py's
sibling idiom), plus T-75-01's fail-closed control: gen_icp_scoring_js.render() must
refuse to generate an artifact from a config whose regions.home is empty/malformed or
whose hard-veto reason is empty -- an empty whitelist would veto every known region (or,
with the veto key vanished, veto none), and a generated workflow Code node must never be
built from that state.
"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gen_icp_scoring_js  # noqa: E402
from src.icp_scoring import load_yaml  # noqa: E402

GENERATED_JS = ROOT / "n8n" / "code" / "icpScoring.generated.js"


def _base_cfg() -> dict:
    return copy.deepcopy(load_yaml("config/icp_scoring.yaml"))


# --- 1. currency: the checked-in generated file is what the generator emits right now ---

def test_icp_scoring_generated_js_currency():
    checked_in = GENERATED_JS.read_text()
    assert gen_icp_scoring_js.render() == checked_in, (
        "n8n/code/icpScoring.generated.js is stale. Regenerate with: "
        ".venv/bin/python scripts/gen_icp_scoring_js.py"
    )


# --- 2. T-75-01 fail-closed control: an empty/malformed whitelist refuses to generate ---

def test_render_raises_when_regions_home_is_empty():
    cfg = _base_cfg()
    cfg["regions"]["home"] = []
    with pytest.raises(AssertionError, match="regions.home"):
        gen_icp_scoring_js.render(cfg)


def test_render_raises_when_regions_home_contains_a_non_string():
    cfg = _base_cfg()
    cfg["regions"]["home"] = ["AU", 7]
    with pytest.raises(AssertionError, match="regions.home"):
        gen_icp_scoring_js.render(cfg)


def test_render_raises_when_a_hard_veto_reason_is_empty():
    cfg = _base_cfg()
    cfg["hard_vetoes"]["outside_home_regions"]["reason"] = ""
    with pytest.raises(AssertionError, match="outside_home_regions"):
        gen_icp_scoring_js.render(cfg)


def test_render_succeeds_against_the_real_config():
    """Vacuity check for the three cases above: render() does NOT reject a healthy
    config wholesale -- the fail-closed asserts are scoped to the specific defect each
    case introduces, not a blanket refusal."""
    assert "const REGIONS_HOME" in gen_icp_scoring_js.render(_base_cfg())
