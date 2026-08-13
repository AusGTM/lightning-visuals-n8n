# tests/test_rubric_change_guard.py
#
# Phase 49 Plan 02, Task 2 (D-09) -- the guard that fails on an unaccompanied rubric
# weight change. Pins config/icp_scoring.yaml's full scoring surface (base_score's four
# tables -- org_type, produces_content, geography, revenue_band -- plus
# graduated_deductions, including its Phase 46 emptiness) as an in-test baseline literal.
#
# This baseline is re-baselined ONLY by an explicit, reviewed act -- never as a routine
# "make the test pass" step. Same idiom as tests/test_companies_factory_frozen.py,
# tests/test_n8n_org_type_absence.py, and tests/test_flow_rubric_conformance.py: a
# permanent guard test over prose, because the parity sweep (scripts/run_scoring_parity.py)
# only detects a rubric/live divergence AFTER it exists and is not currently running on any
# cadence (D-09's own rejection of relying on the sweep as the detector). The reviewed
# re-baseline act that unpins this test includes running the re-score docs/OPERATOR-RESCORE.md
# describes -- updating the literal below without running that re-score is exactly the
# unaccompanied change this guard exists to block.
#
# Offline only: no network, no HubSpot credentials, no src.hubspot_client import.
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
RUBRIC_PATH = ROOT / "config" / "icp_scoring.yaml"
RUNBOOK_PATH = "docs/OPERATOR-RESCORE.md"

# Pinned 2026-08-13 against config/icp_scoring.yaml (Phase 46, commit caae5d6):
# individual_club_team raised 5->15, regulator dropped 0->-20, and the gambling
# graduated deduction fully removed (graduated_deductions is pinned EMPTY on purpose --
# a re-introduced key must also fail this guard).
PINNED_BASE_SCORE = {
    "org_type": {
        "governing_body_league": 40,
        "content_producer": 20,
        "broadcaster": 20,
        "individual_club_team": 15,
        "regulator": -20,
        "gambling_operator": 0,
        "hardware_vendor": 0,
        "other": 0,
        "unknown": 0,
    },
    "produces_content": {True: 20, False: 0, "unknown": 0},
    "geography": {"ANZ": 10, "AU": 10, "NZ": 10, "non_anz": 0, "unknown": 0},
    "revenue_band": {
        "<1M": 0,
        "1-5M": 0,
        "5-50M": 10,
        "50-500M": 10,
        "500-750M": -5,
        "750M-1B": -15,
        "1B-1.2B": -30,
        "1.2B+": -50,
        "unknown": 0,
    },
}
PINNED_GRADUATED_DEDUCTIONS = {}


def load_rubric() -> dict:
    with RUBRIC_PATH.open() as f:
        return yaml.safe_load(f)


def _diff_keys(pinned: dict, actual: dict) -> list:
    """Returns a sorted list of 'component.key' strings for every entry that differs
    (missing, added, or changed value) between the two mappings, one level deep per
    base_score component plus graduated_deductions -- so the failure message can name
    exactly what moved without the next engineer re-reading the whole file."""
    diffs = []
    all_keys = set(pinned) | set(actual)
    for key in sorted(all_keys, key=str):
        if pinned.get(key, object()) != actual.get(key, object()):
            diffs.append(str(key))
    return diffs


def assert_rubric_pinned(config: dict) -> None:
    """RED (Task 49-02-02): stub -- not yet implemented. Comparison logic lands in the
    GREEN commit. This stub deliberately never raises, so every mutation test below
    (which expects an AssertionError) fails until the real comparison is written."""
    # ponytail: RED stub, GREEN commit replaces this with the real comparison.
    return None


def test_pinned_rubric_matches_current_config():
    """Passes today against the live config/icp_scoring.yaml -- proves the pin is
    accurate, not merely present."""
    assert_rubric_pinned(load_rubric())


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda cfg: cfg["base_score"]["org_type"].__setitem__("regulator", -25),
            id="org_type_weight_changed",
        ),
        pytest.param(
            lambda cfg: cfg["base_score"]["revenue_band"].__setitem__("5-50M", 15),
            id="revenue_band_weight_changed",
        ),
        pytest.param(
            lambda cfg: cfg["base_score"]["geography"].__setitem__("non_anz", 5),
            id="geography_weight_changed",
        ),
        pytest.param(
            lambda cfg: cfg["graduated_deductions"].__setitem__("gambling_operator", -10),
            id="graduated_deduction_reintroduced",
        ),
    ],
)
def test_mutated_rubric_fails_the_guard(mutate):
    """Each mutation case demonstrates the guard has teeth: a copy of the loaded config,
    with exactly one value changed, must fail assert_rubric_pinned. Covers an org_type
    weight, a revenue_band weight, a geography weight, and a re-introduced graduated
    deduction (the Phase 46 removal is part of what is pinned, per the guard's own
    docstring)."""
    config = load_rubric()
    mutate(config)
    with pytest.raises(AssertionError):
        assert_rubric_pinned(config)


def test_failure_message_names_runbook_and_rescore_obligation():
    """A future refactor of assert_rubric_pinned's message text cannot silently drop the
    pointer to docs/OPERATOR-RESCORE.md or the re-score obligation -- this is asserted
    directly against the raised message, not by inspection of the source."""
    config = load_rubric()
    config["base_score"]["org_type"]["regulator"] = -999
    with pytest.raises(AssertionError) as excinfo:
        assert_rubric_pinned(config)
    message = str(excinfo.value)
    assert RUNBOOK_PATH in message
    assert "re-score" in message.lower()
