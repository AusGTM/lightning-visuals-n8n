#!/usr/bin/env python3
# scripts/gen_hubspot_enums_js.py
#
# Generates n8n/code/hubspotEnums.generated.js from the pinned HubSpot company property
# schema snapshot. n8n Code nodes cannot read files at runtime (spec AR-4), so what
# HubSpot's enumeration properties accept must be inlined as JS literals -- but GENERATED
# literals, never hand-typed, the same rule scripts/gen_taxonomy_js.py already follows.
#
# Run directly to (re)write the checked-in file:
#   .venv/bin/python scripts/gen_hubspot_enums_js.py
# scripts/build_cloud_workflows.py also calls render() before inlining, so a stale
# generated file can never survive a rebuild -- but the checked-in copy still needs
# regenerating by hand after a snapshot refresh; the currency test in
# tests/test_hubspot_enums_generated_currency.py is what catches forgetting to.
#
# ponytail: json.dumps handles all JS-literal escaping -- no hand-built string templates,
# no second escape path (same rule gen_taxonomy_js.py and build_cloud_workflows.py follow).
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The 2026-08-03 live-verified snapshot: `industry` carries 148 options and `SPORTS` is
# among them (tests/test_hubspot_enums_generated_currency.py pins this fidelity fact).
SNAPSHOT = "config/hubspot_migration/baseline/portal-schema-companies-post-orgtype-enum.json"

# Exactly the DEFAULT_COMPANY_POLICY keys (n8n/code/mergeCompanies.js) whose snapshot
# `type` is `enumeration`. Nothing else is emitted -- this file is inlined into every
# workflow node that carries mergeCompanies, and the companies schema has dozens of
# unrelated enumeration properties this repo never validates.
# Kept in sync with config/field_policy.yaml `companies` + the snapshot by
# tests/test_hubspot_enums_generated_currency.py's policy-pin test.
ENUM_PROPERTIES = [
    "industry",
    "lv_org_type",
    "lv_content_type",
    "lv_revenue_band",
    "lv_employee_band",
    "lv_country_region_normalized",
]

OUT = ROOT / "n8n" / "code" / "hubspotEnums.generated.js"


def _load_snapshot(snapshot_path: Path) -> dict:
    data = json.loads(snapshot_path.read_text())
    return {p["name"]: p for p in data["results"]}


def _property_entry(name: str, prop: dict) -> dict:
    if prop.get("type") != "enumeration":
        raise SystemExit(
            f"{name} is not type=enumeration in the pinned snapshot (got {prop.get('type')!r}) "
            "-- a silently-empty option set would validate nothing while looking healthy."
        )
    options = prop.get("options") or []
    multi_select = prop.get("fieldType") == "checkbox"
    values = [o["value"] for o in options]
    label_to_value = {str(o["label"]).lower(): o["value"] for o in options}
    return {"multiSelect": multi_select, "values": values, "labelToValue": label_to_value}


def render(snapshot_name: str = SNAPSHOT) -> str:
    props = _load_snapshot(ROOT / snapshot_name)

    entries = {}
    for name in ENUM_PROPERTIES:
        prop = props.get(name)
        if prop is None:
            raise SystemExit(f"{name} is absent from {snapshot_name}")
        entries[name] = _property_entry(name, prop)

    lines = [
        "// n8n/code/hubspotEnums.generated.js",
        "//",
        f"// GENERATED FROM {snapshot_name} — DO NOT EDIT.",
        "// Regenerate with: .venv/bin/python scripts/gen_hubspot_enums_js.py",
        "//",
        "// Values AND labels for every HubSpot company enumeration property this repo",
        "// validates candidates against — see n8n/code/hubspotEnums.js for the",
        "// hand-written normalizer logic that consumes this module.",
        "",
        f"const HUBSPOT_ENUM_SNAPSHOT = {json.dumps(snapshot_name)};",
        "",
        f"const COMPANY_ENUM_PROPERTIES = {json.dumps(entries, indent=2)};",
        "",
        "module.exports = {",
        "  HUBSPOT_ENUM_SNAPSHOT,",
        "  COMPANY_ENUM_PROPERTIES,",
        "};",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=SNAPSHOT,
                         help="repo-relative path to the schema snapshot JSON")
    args = parser.parse_args()
    OUT.write_text(render(args.snapshot))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
