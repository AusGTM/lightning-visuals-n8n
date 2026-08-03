"""Phase 31 Plan 03 Task 1 — the closing contract inventory.

Per HANDOFF.md §2 item 2 / §3 BUG 31 (four-then-five recorded instances of "a contract
held in two places, tested on only one side") and 31-CONTEXT.md's process invariant:
every contract this phase touched must be pinned by a test that reads BOTH sides.

This file does not re-implement any of those pins — `operator-claude-plugin/tests/
test_control_flag_parity.py` established the idiom, and `tests/
test_hubspot_enums_generated_currency.py` / `operator-claude-plugin/tests/
test_review_outcome_parity.py` (31-01, 31-02) already ARE the two pins for four of the
five rows below. Re-asserting the contracts here would be a sixth instance of the exact
defect this phase closes. Instead, this is an INVENTORY GUARD: it fails when a phase-31
pin — or one of the source/committed files a row names — is deleted or renamed without
this table being updated.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# One row per contract phase 31 created or changed. `sides` names the two (or three)
# artifacts that must agree; `pinned_by` is the test file that reads all of them.
PHASE_31_CONTRACTS = [
    {
        "name": "pinned HubSpot schema snapshot <-> hubspotEnums.generated.js",
        "sides": [
            "config/hubspot_migration/baseline/portal-schema-companies-post-orgtype-enum.json",
            "n8n/code/hubspotEnums.generated.js",
        ],
        "pinned_by": "tests/test_hubspot_enums_generated_currency.py",
    },
    {
        "name": "DEFAULT_COMPANY_POLICY's enumeration-typed keys <-> gen_hubspot_enums_js.ENUM_PROPERTIES",
        "sides": [
            "n8n/code/mergeCompanies.js",
            "scripts/gen_hubspot_enums_js.py",
        ],
        "pinned_by": "tests/test_hubspot_enums_generated_currency.py",
    },
    {
        "name": "reviewApply's `invalid` return key <-> reviewDecision's consumption of it",
        "sides": [
            "n8n/code/reviewApply.js",
            "n8n/code/reviewDecision.js",
        ],
        "pinned_by": "tests/n8n/hubspotEnumValidation.test.mjs",
    },
    {
        "name": "reviewDecision.js outcome words <-> committed wf_review_decision_cloud.json node <-> client OUTCOMES tuple",
        "sides": [
            "n8n/code/reviewDecision.js",
            "n8n/wf_review_decision_cloud.json",
            "operator-claude-plugin/scripts/review_decision.py",
        ],
        "pinned_by": "operator-claude-plugin/tests/test_review_outcome_parity.py",
    },
    {
        "name": "Build Review Decision allowlist pre-check <-> committed Review Decision Update Write Gate",
        "sides": [
            "scripts/build_cloud_workflows.py",
            "n8n/wf_review_decision_cloud.json",
        ],
        "pinned_by": "tests/n8n/reviewAllowlistRefusal.test.mjs",
    },
]


def test_phase_31_contracts_table_has_exactly_the_five_recorded_rows():
    assert len(PHASE_31_CONTRACTS) == 5
    for row in PHASE_31_CONTRACTS:
        assert len(row["sides"]) >= 2, row["name"]
        assert row["pinned_by"], row["name"]


def test_every_pin_named_in_the_table_exists_on_disk_and_is_non_empty():
    seen = {row["pinned_by"] for row in PHASE_31_CONTRACTS}
    assert len(seen) >= 3, "the five rows should be covered by more than one test file"
    for pin in seen:
        path = ROOT / pin
        assert path.is_file(), f"pinning test file missing: {pin}"
        assert path.stat().st_size > 0, f"pinning test file is empty: {pin}"


def test_every_side_named_in_the_table_exists_on_disk():
    for row in PHASE_31_CONTRACTS:
        for side in row["sides"]:
            path = ROOT / side
            assert path.is_file(), f"{row['name']}: side file missing: {side}"
