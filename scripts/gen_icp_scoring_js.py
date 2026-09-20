#!/usr/bin/env python3
# scripts/gen_icp_scoring_js.py
#
# Generates n8n/code/icpScoring.generated.js from config/icp_scoring.yaml. n8n Code
# nodes cannot read files at runtime (spec AR-4), so the region whitelist, region
# aliases, hard-veto reason strings and geography point table must be inlined as JS
# literals — but GENERATED literals, never hand-typed (Phase 12 D3 precedent, mirrored
# from scripts/gen_escalation_js.py). This is the one script that produces them.
#
# Run directly to (re)write the checked-in file:
#   .venv/bin/python scripts/gen_icp_scoring_js.py
# scripts/build_cloud_workflows.py also calls render() before inlining, so a stale
# generated file can never survive a rebuild — but the checked-in copy still needs
# regenerating by hand after an icp_scoring.yaml edit; the currency test in
# tests/test_icp_scoring_generated_currency.py is what catches forgetting to.
#
# ponytail: json.dumps handles all JS-literal escaping — no hand-built string
# templates, no second escape path (same rule build_cloud_workflows.py already follows).
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.icp_scoring import load_yaml  # noqa: E402

OUT = ROOT / "n8n" / "code" / "icpScoring.generated.js"


def render(cfg: dict = None) -> str:
    """T-75-01 (Denial of Service, mitigate): a malformed or empty `regions.home` would
    make every KNOWN region "other" -- vetoing the entire population -- or, if the veto
    key vanished, veto none at all. Fail closed rather than default: refuse to generate
    a workflow-embeddable artifact from a whitelist that could do either. `cfg` is
    optional (mirrors compute_icp_score's cfg= idiom) so a caller can inject an in-memory
    config to exercise these assertions without editing the shipped yaml
    (tests/test_icp_scoring_generated_currency.py's fail-closed cases)."""
    cfg = cfg if cfg is not None else load_yaml("config/icp_scoring.yaml")

    regions_home = cfg.get("regions", {}).get("home")
    assert isinstance(regions_home, list) and len(regions_home) > 0, (
        "config/icp_scoring.yaml regions.home must be a non-empty list — an empty or "
        "absent whitelist would veto every known region"
    )
    for member in regions_home:
        assert isinstance(member, str) and member, (
            f"config/icp_scoring.yaml regions.home contains a non-string/empty member: {member!r}"
        )

    hard_vetoes = cfg.get("hard_vetoes", {})
    for key, entry in hard_vetoes.items():
        reason = entry.get("reason") if isinstance(entry, dict) else None
        assert isinstance(reason, str) and reason, (
            f"config/icp_scoring.yaml hard_vetoes.{key}.reason is absent or empty"
        )

    region_aliases = cfg.get("regions", {}).get("aliases", {})
    hard_veto_reasons = {key: entry["reason"] for key, entry in hard_vetoes.items()}
    geography_points = cfg["base_score"]["geography"]

    lines = [
        "// n8n/code/icpScoring.generated.js",
        "//",
        "// GENERATED FROM config/icp_scoring.yaml — DO NOT EDIT.",
        "// Regenerate with: .venv/bin/python scripts/gen_icp_scoring_js.py",
        "//",
        "// Region whitelist / veto reason / geography point data only — see",
        "// scripts/build_cloud_workflows.py's ENRICH_DECIDE_CO_CLOUD for the",
        "// hand-written logic that consumes this module.",
        "",
        f"const VERSION = {json.dumps(cfg.get('version', 'unknown'))};",
        "",
        f"const REGIONS_HOME = {json.dumps(regions_home, indent=2)};",
        "",
        f"const REGION_ALIASES = {json.dumps(region_aliases, indent=2)};",
        "",
        f"const HARD_VETO_REASONS = {json.dumps(hard_veto_reasons, indent=2)};",
        "",
        f"const GEOGRAPHY_POINTS = {json.dumps(geography_points, indent=2)};",
        "",
        "module.exports = {",
        "  VERSION,",
        "  REGIONS_HOME,",
        "  REGION_ALIASES,",
        "  HARD_VETO_REASONS,",
        "  GEOGRAPHY_POINTS,",
        "};",
        "",
    ]
    return "\n".join(lines)


def main():
    OUT.write_text(render())
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
