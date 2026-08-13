#!/usr/bin/env python3
# scripts/gen_taxonomy_js.py
#
# Generates n8n/code/taxonomy.generated.js from config/taxonomy.yaml. n8n Code nodes
# cannot read files at runtime (spec AR-4), so the vocabulary must be inlined as JS
# literals — but GENERATED literals, never hand-typed (spec TX-4). This is the one
# script that produces them.
#
# Run directly to (re)write the checked-in file:
#   .venv/bin/python scripts/gen_taxonomy_js.py
# scripts/build_cloud_workflows.py also calls render() before inlining, so a stale
# generated file can never survive a rebuild — but the checked-in copy still needs
# regenerating by hand after a taxonomy.yaml edit; the currency test in
# tests/test_taxonomy_conformance.py is what catches forgetting to.
#
# ponytail: json.dumps handles all JS-literal escaping — no hand-built string
# templates, no second escape path (same rule build_cloud_workflows.py already follows).
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.taxonomy import (  # noqa: E402
    CONTENT_TYPES,
    DEFAULT_CONTENT_TYPE,
    DEFAULT_ORG_TYPE,
    EVIDENCE_GATED_ORG_TYPES,
    ORG_TYPE_DEFINITIONS,
    ORG_TYPES,
    VERSION,
    normalize_key,
)

OUT = ROOT / "n8n" / "code" / "taxonomy.generated.js"


def _synonym_map(vocab: dict) -> dict:
    # normalized-synonym -> canonical. Only literal synonyms from the YAML — the
    # canonical keys themselves are not folded in here; taxonomy.js's normalizer
    # (hand-written logic, D2) checks canonical keys separately so the generated
    # data stays pure vocabulary, no derived lookup shortcuts baked into the file.
    table = {}
    for canonical, spec in vocab.items():
        for syn in spec.get("synonyms") or []:
            table[normalize_key(syn)] = canonical
    return table


def render() -> str:
    org_types = list(ORG_TYPES)
    content_types = list(CONTENT_TYPES)
    org_synonyms = _synonym_map(ORG_TYPES)
    content_synonyms = _synonym_map(CONTENT_TYPES)
    content_implies = {k: v.get("implies_content") for k, v in CONTENT_TYPES.items()}

    lines = [
        "// n8n/code/taxonomy.generated.js",
        "//",
        "// GENERATED FROM config/taxonomy.yaml — DO NOT EDIT.",
        f"// taxonomy version: {VERSION}",
        "// Regenerate with: .venv/bin/python scripts/gen_taxonomy_js.py",
        "//",
        "// Vocabulary data only (spec D2) — see n8n/code/taxonomy.js for the",
        "// hand-written normalizer logic that consumes this module.",
        "",
        f"const TAXONOMY_VERSION = {json.dumps(VERSION)};",
        "",
        f"const ORG_TYPES = {json.dumps(org_types, indent=2)};",
        "",
        # TX-10 (Phase 49 Plan 03): mirrors src.taxonomy.ORG_TYPE_DEFINITIONS so the n8n
        # research prompt can carry the same discriminators as both Python prompts
        # (org_type_definitions_block()) instead of a bare key list.
        f"const ORG_TYPE_DEFINITIONS = {json.dumps(ORG_TYPE_DEFINITIONS, indent=2)};",
        "",
        f"const ORG_TYPE_SYNONYMS = {json.dumps(org_synonyms, indent=2)};",
        "",
        f"const EVIDENCE_GATED_ORG_TYPES = {json.dumps(EVIDENCE_GATED_ORG_TYPES, indent=2)};",
        "",
        f"const DEFAULT_ORG_TYPE = {json.dumps(DEFAULT_ORG_TYPE)};",
        "",
        f"const CONTENT_TYPES = {json.dumps(content_types, indent=2)};",
        "",
        f"const CONTENT_TYPE_SYNONYMS = {json.dumps(content_synonyms, indent=2)};",
        "",
        f"const CONTENT_TYPE_IMPLIES = {json.dumps(content_implies, indent=2)};",
        "",
        f"const DEFAULT_CONTENT_TYPE = {json.dumps(DEFAULT_CONTENT_TYPE)};",
        "",
        "module.exports = {",
        "  TAXONOMY_VERSION,",
        "  ORG_TYPES,",
        "  ORG_TYPE_DEFINITIONS,",
        "  ORG_TYPE_SYNONYMS,",
        "  EVIDENCE_GATED_ORG_TYPES,",
        "  DEFAULT_ORG_TYPE,",
        "  CONTENT_TYPES,",
        "  CONTENT_TYPE_SYNONYMS,",
        "  CONTENT_TYPE_IMPLIES,",
        "  DEFAULT_CONTENT_TYPE,",
        "};",
        "",
    ]
    return "\n".join(lines)


def main():
    OUT.write_text(render())
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
