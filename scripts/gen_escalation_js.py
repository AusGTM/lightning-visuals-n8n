#!/usr/bin/env python3
# scripts/gen_escalation_js.py
#
# Generates n8n/code/escalation.generated.js from config/escalation_policy.yaml. n8n Code
# nodes cannot read files at runtime (spec AR-4), so the thresholds must be inlined as JS
# literals — but GENERATED literals, never hand-typed (Phase 12 D3 precedent, reused
# verbatim). This is the one script that produces them.
#
# Run directly to (re)write the checked-in file:
#   .venv/bin/python scripts/gen_escalation_js.py
# scripts/build_cloud_workflows.py also calls render() before inlining, so a stale
# generated file can never survive a rebuild — but the checked-in copy still needs
# regenerating by hand after an escalation_policy.yaml edit; the currency test in
# tests/test_judge_spec.py is what catches forgetting to.
#
# ponytail: json.dumps handles all JS-literal escaping — no hand-built string
# templates, no second escape path (same rule build_cloud_workflows.py already follows).
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.judge import (  # noqa: E402
    ESCALATION_CONFIDENCE_BAND,
    JUDGE_MIN_CONFIDENCE,
    JUDGE_OUTPUT_REQUIRED,
    KNOWN_VIDEO_HOSTS,
)

OUT = ROOT / "n8n" / "code" / "escalation.generated.js"


def render() -> str:
    lines = [
        "// n8n/code/escalation.generated.js",
        "//",
        "// GENERATED FROM config/escalation_policy.yaml — DO NOT EDIT.",
        "// Regenerate with: .venv/bin/python scripts/gen_escalation_js.py",
        "//",
        "// Threshold/vocabulary data only — see n8n/code/judge.js for the hand-written",
        "// trigger logic that consumes this module.",
        "",
        f"const ESCALATION_CONFIDENCE_BAND = {json.dumps(ESCALATION_CONFIDENCE_BAND)};",
        "",
        f"const JUDGE_MIN_CONFIDENCE = {json.dumps(JUDGE_MIN_CONFIDENCE)};",
        "",
        f"const JUDGE_OUTPUT_REQUIRED = {json.dumps(JUDGE_OUTPUT_REQUIRED, indent=2)};",
        "",
        f"const KNOWN_VIDEO_HOSTS = {json.dumps(KNOWN_VIDEO_HOSTS, indent=2)};",
        "",
        "module.exports = {",
        "  ESCALATION_CONFIDENCE_BAND,",
        "  JUDGE_MIN_CONFIDENCE,",
        "  JUDGE_OUTPUT_REQUIRED,",
        "  KNOWN_VIDEO_HOSTS,",
        "};",
        "",
    ]
    return "\n".join(lines)


def main():
    OUT.write_text(render())
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
