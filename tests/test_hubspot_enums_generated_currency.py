"""Phase 31 Task 3 — pin n8n/code/hubspotEnums.generated.js to the pinned schema snapshot,
and pin the generator's property list to the field policy + the snapshot itself.

Mirrors tests/test_taxonomy_conformance.py::test_taxonomy_generated_js_currency (the
render()-vs-checked-in-text idiom) and operator-claude-plugin/tests/test_control_flag_
parity.py (the read-the-other-side-as-TEXT idiom for a contract held in two places).

Three tests, each a DRIFT GUARD:
  1. currency    — the checked-in generated file is byte-identical to what the generator
                    would emit right now (ROADMAP criterion 1's drift gate).
  2. policy pin  — gen_hubspot_enums_js.ENUM_PROPERTIES cannot drift from
                    DEFAULT_COMPANY_POLICY's own enumeration-typed keys, read as TEXT
                    (never imported), against the pinned snapshot's own `type` field.
  3. fidelity    — the live 2026-08-03 finding (industry has 148 options, SPORTS is one
                    of them, the offending provider label matches neither a value nor a
                    label) is pinned against the SNAPSHOT so a future snapshot refresh
                    that quietly changes it fails loudly.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gen_hubspot_enums_js  # noqa: E402

MERGE_COMPANIES_JS = ROOT / "n8n" / "code" / "mergeCompanies.js"
GENERATED_JS = ROOT / "n8n" / "code" / "hubspotEnums.generated.js"


def _snapshot() -> dict:
    data = json.loads((ROOT / gen_hubspot_enums_js.SNAPSHOT).read_text())
    return {p["name"]: p for p in data["results"]}


# --- 1. currency: the checked-in generated file is what the generator emits right now ---

def test_hubspot_enums_generated_js_currency():
    checked_in = GENERATED_JS.read_text()
    assert gen_hubspot_enums_js.render() == checked_in, (
        "n8n/code/hubspotEnums.generated.js is stale. Regenerate with: "
        ".venv/bin/python scripts/gen_hubspot_enums_js.py"
    )


# --- 2. the two-sided policy pin: mergeCompanies.js (as TEXT) + the snapshot -----------

def test_enum_properties_matches_field_policy_enumeration_keys():
    """gen_hubspot_enums_js.ENUM_PROPERTIES is a hand-written copy of a fact that lives in
    TWO other files: DEFAULT_COMPANY_POLICY's key set (mergeCompanies.js) and each key's
    `type` in the pinned schema snapshot. Read mergeCompanies.js as TEXT (never imported —
    this file must not require a JS runtime) so a policy key added there and not mirrored
    into the generator's list fails here, the milestone's five-times-burned rule applied
    to this specific contract.
    """
    src = MERGE_COMPANIES_JS.read_text()
    block = src.split("const DEFAULT_COMPANY_POLICY = {", 1)[1].split("\n};", 1)[0]
    policy_keys = set(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*):\s*\{", block, re.MULTILINE))
    assert policy_keys, "failed to extract any DEFAULT_COMPANY_POLICY keys from mergeCompanies.js"

    snapshot = _snapshot()
    expected = {k for k in policy_keys if snapshot.get(k, {}).get("type") == "enumeration"}

    assert expected == set(gen_hubspot_enums_js.ENUM_PROPERTIES), (
        f"gen_hubspot_enums_js.ENUM_PROPERTIES has drifted from DEFAULT_COMPANY_POLICY's "
        f"enumeration-typed keys — missing from ENUM_PROPERTIES: "
        f"{sorted(expected - set(gen_hubspot_enums_js.ENUM_PROPERTIES))}; "
        f"extra in ENUM_PROPERTIES: {sorted(set(gen_hubspot_enums_js.ENUM_PROPERTIES) - expected)}"
    )


# --- 3. fidelity spot-check against the SNAPSHOT (not the generated file) --------------

def test_snapshot_industry_fidelity_matches_the_live_2026_08_03_finding():
    industry = _snapshot()["industry"]
    options = industry["options"]

    assert len(options) == 148, (
        f"the pinned snapshot's industry property now has {len(options)} options, not "
        "148 — the live-verified 2026-08-03 finding this test pins has changed; confirm "
        "the new count is correct before updating this assertion"
    )
    values = {o["value"] for o in options}
    assert "SPORTS" in values

    offending = "arts, entertainment, and recreation"
    labels_lower = {o["label"].lower() for o in options}
    values_lower = {v.lower() for v in values}
    assert offending not in labels_lower
    assert offending not in values_lower
