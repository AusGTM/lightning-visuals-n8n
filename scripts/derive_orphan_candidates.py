#!/usr/bin/env python3
"""scripts/derive_orphan_candidates.py

Phase 42 Plan 03 (D-02/D-03) — the fail-safe orphan-candidacy derivation tool.

Default mode is a read-only report: enumerate live company properties and automation
flows via the portal API, cross-reference every name against this repo's executable
surfaces, and classify each as `protected`, `referenced`, `ambiguous`, or
`uncontested_orphan`. Nothing is mutated unless `--archive` is passed AND both
`DRY_RUN=false` and `ALLOW_HUBSPOT_PROPERTY_ARCHIVE=true` are set (the same two-key gate
idiom as scripts/sync_hubspot_properties.py and scripts/put_hubspot_flow.py).

F1/F4 — the do-not-archive set is IMPORTED from scripts/check_schema_drift.py, never
restated here. A second copy of that constant is a constant that can silently drift out of
agreement with the one the drift checker enforces, and this repo's only pre-existing
reference detector (tests/test_hubspot_schema_coverage.py `PROPERTY_RE`) uses a
`lv_`/`enrichment_` namespace-prefix regex that structurally cannot match the five
`*_score` component properties — a detector built by copying that pattern would classify
the live scoring engine as unreferenced and hand it to the archival path. This tool's
`classify_candidate` checks the do-not-archive set, the declared-in-yaml set, and the live
`calculationFormula` substring set BEFORE any reference scan result can matter.

D-03 — "archive uncontested, ask on doubt". `classify_candidate`'s default branch is
`ambiguous`, never `uncontested_orphan`. "Uncontested" is coded, not a judgement call: zero
executable references AND zero test references AND a `DISPOSABLE_PROVENANCE_PATTERNS`
match. `archive_property` raises for anything else.

`.env` is Read/Bash permission-blocked this session — the operator invocation is:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['derive_orphan_candidates.py', '--out', 'PATH/TO/report.json']; \
         runpy.run_path('scripts/derive_orphan_candidates.py', run_name='__main__')"

Usage:
    python scripts/derive_orphan_candidates.py --out PATH [--archive]
"""
import argparse
import functools
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve
sys.path.insert(0, str(ROOT / "scripts"))  # so `check_schema_drift` resolves as a module

from check_schema_drift import (  # noqa: E402
    DO_NOT_ARCHIVE_COMPANY_PROPERTIES,
    DO_NOT_ARCHIVE_FLOW_IDS,
    _assert_no_secrets,
    _get_live_flows,
    _get_live_properties,
    _has_credentials,
    _portal_ok,
)

CONFIG_PATH = ROOT / "config" / "hubspot_properties.yaml"
ARCHIVE_DIR = ROOT / "config" / "hubspot_flows" / "archive-2026-08-07"

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

# HubSpot's object-type id for companies (confirmed live in every fetched flow under
# config/hubspot_flows/*.json). CLEAN-01 is company-scoring scoped (42-CONTEXT.md D-04);
# a flow targeting any other object type is out_of_scope, never archived by this tool.
COMPANY_OBJECT_TYPE_ID = "0-2"

THIS_FILE = Path(__file__).resolve()
TEST_FILE = (ROOT / "tests" / "test_orphan_candidates.py").resolve()

# Executable surfaces this tool scans as free text for a name occurrence. Deliberately
# excludes `.planning/**` and every markdown file (planning prose is context, never
# evidence of reference or non-reference -- the trap 39-DECISION.md's superseded sentence
# sets). scripts/*.py and src/*.py cover the codebase's only two flat Python source trees
# (confirmed flat, no nested subpackages, at authoring time); config/hubspot_flows/**/*.json
# is scanned whole so the calculationFormula string field -- which a structural key-walker
# would never see -- is covered by the same free-text pass as branch filters.
EXECUTABLE_SURFACE_GLOBS = (
    "config/hubspot_flows/**/*.json",
    "n8n/code/*.js",
    "n8n/wf_*.json",
    "scripts/*.py",
    "src/*.py",
    "config/*.yaml",
    "config/*.json",
)

# Test-file hits are a distinct, weaker signal (module docstring / plan): they prove
# something is asserted about, never that anything live depends on it. A property with
# only test refs is `ambiguous`, never `uncontested_orphan`.
TEST_SURFACE_GLOBS = ("tests/*.py",)

# Node types that are documentation pinned to a canvas, not executable parameters. Mirrors
# tests/test_hubspot_schema_coverage.py's own exclusion set exactly -- without it, a sticky
# note's prose asserting "X is never referenced" would itself register as a reference.
NON_EXECUTABLE_NODE_TYPES = {"n8n-nodes-base.stickyNote"}

# D-03's coded definition of "uncontested": self-evidently throwaway provenance. Each entry
# is commented with the concrete repo precedent it matches -- this tuple IS the answer to
# "what counts as obvious provenance", never left to an executor's on-the-spot judgement.
DISPOSABLE_PROVENANCE_PATTERNS = (
    # scripts/probe_org_type_migration.py PROBE_PROPERTY_NAME =
    # "lv__phase21_org_type_probe" -- this repo's double-underscored phase-probe naming
    # convention for a disposable property created solely to settle an open question and
    # torn down in the same run.
    re.compile(r"^[a-z0-9]+__phase\d+_.*probe", re.IGNORECASE),
    # The same convention's general form: a bare trailing "_probe" suffix, for a probe
    # artifact that did not carry the double-underscore phase-number prefix.
    re.compile(r"_probe$", re.IGNORECASE),
    # scripts/probe_scoring_recalc_latency.py COMPANY_NAME_PREFIX =
    # "ZZ-SCORING-TEST-DELETE-ME-" -- Phase 40's disposable test-record prefix. Applies if
    # a property or flow name itself carries this test-record naming convention.
    re.compile(r"^ZZ-SCORING-TEST-DELETE-ME-", re.IGNORECASE),
)


def _has_disposable_provenance(name: str) -> bool:
    return any(p.search(name) for p in DISPOSABLE_PROVENANCE_PATTERNS)


def _name_pattern(name: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(name) + r"\b")


def _strip_sticky_notes(doc):
    """Pure, offline-testable. Removes sticky-note nodes from an n8n-shaped workflow doc
    before it is scanned as text. A no-op for any doc without a top-level `nodes` list
    (e.g. HubSpot flow JSON, which uses `actions`, not `nodes`)."""
    if isinstance(doc, dict) and isinstance(doc.get("nodes"), list):
        doc = dict(doc)
        doc["nodes"] = [n for n in doc["nodes"] if n.get("type") not in NON_EXECUTABLE_NODE_TYPES]
    return doc


def _text_for_scan(path: Path) -> str:
    if path.suffix == ".json":
        try:
            doc = json.loads(path.read_text())
        except json.JSONDecodeError:
            return path.read_text()
        doc = _strip_sticky_notes(doc)
        return json.dumps(doc)
    return path.read_text()


def _iter_glob_files(globs, exclude):
    seen = set()
    for pattern in globs:
        for path in sorted(ROOT.glob(pattern)):
            resolved = path.resolve()
            if resolved in exclude or resolved in seen or not path.is_file():
                continue
            seen.add(resolved)
            yield path


def _iter_executable_files():
    yield from _iter_glob_files(EXECUTABLE_SURFACE_GLOBS, {THIS_FILE})


def _iter_test_files():
    yield from _iter_glob_files(TEST_SURFACE_GLOBS, {TEST_FILE})


@functools.lru_cache(maxsize=1)
def _get_surface_texts():
    executable = {p: _text_for_scan(p) for p in _iter_executable_files()}
    test = {p: _text_for_scan(p) for p in _iter_test_files()}
    return executable, test


def _scan_references(name: str) -> dict:
    """`{executable: [relative paths], test: [relative paths]}` -- every surface where
    `name` appears as a whole-token free-text match. Network-free; reads only committed
    repo files."""
    executable_texts, test_texts = _get_surface_texts()
    pattern = _name_pattern(name)
    return {
        "executable": sorted(str(p.relative_to(ROOT)) for p, text in executable_texts.items() if pattern.search(text)),
        "test": sorted(str(p.relative_to(ROOT)) for p, text in test_texts.items() if pattern.search(text)),
    }


def _live_calculation_formulas(live_properties: list) -> list:
    return [p["calculationFormula"] for p in live_properties
            if p.get("calculated") and p.get("calculationFormula")]


def _protected_by(name: str, formulas: list, declared_names: set) -> str | None:
    if name in DO_NOT_ARCHIVE_COMPANY_PROPERTIES:
        return "do_not_archive_set"
    if name in declared_names:
        return "declared_in_yaml"
    if any(_name_pattern(name).search(f) for f in formulas):
        return "calculation_formula"
    return None


def classify_candidate(name: str, refs: dict, formulas: list, declared_names: set) -> str:
    """Pure, offline-testable, network-free. Evaluated in this exact precedence order --
    the ordering IS the safety property, since every protective branch must be reached
    before any archivable verdict becomes possible.

    1. protected  -- do-not-archive set, OR declared in config/hubspot_properties.yaml,
                      OR named in a live calculationFormula string
    2. referenced -- any executable-surface hit
    3. uncontested_orphan -- zero executable hits AND zero test hits AND a
                      DISPOSABLE_PROVENANCE_PATTERNS match
    4. ambiguous  -- default, fail-safe
    """
    if _protected_by(name, formulas, declared_names) is not None:
        return "protected"
    if refs.get("executable"):
        return "referenced"
    if not refs.get("executable") and not refs.get("test") and _has_disposable_provenance(name):
        return "uncontested_orphan"
    return "ambiguous"


def classify_flow(flow: dict, refs: dict) -> str:
    """Same precedence discipline as classify_candidate, specialised for automation flows.
    A flow id in the do-not-archive set is protected regardless of anything else; a flow
    targeting a non-company object is out_of_scope (CLEAN-01 is company-scoring scoped)."""
    flow_id = str(flow.get("id"))
    if flow_id in DO_NOT_ARCHIVE_FLOW_IDS:
        return "protected"
    if flow.get("objectTypeId") != COMPANY_OBJECT_TYPE_ID:
        return "out_of_scope"
    if refs.get("executable"):
        return "referenced"
    name = flow.get("name", "")
    if not refs.get("executable") and not refs.get("test") and _has_disposable_provenance(name):
        return "uncontested_orphan"
    return "ambiguous"


def build_candidate_report(live_companies: list, live_flows: list, declared_names: set,
                            portal_id: str | None) -> dict:
    formulas = _live_calculation_formulas(live_companies)
    summary: dict = defaultdict(int)

    properties_report = []
    for prop in sorted(live_companies, key=lambda p: p["name"]):
        if prop.get("hubspotDefined"):
            continue  # native HubSpot fields are never candidates -- they are out of D-02's scope entirely
        name = prop["name"]
        refs = _scan_references(name)
        classification = classify_candidate(name, refs, formulas, declared_names)
        summary[classification] += 1
        properties_report.append({
            "name": name,
            "classification": classification,
            "executable_refs": refs["executable"],
            "test_refs": refs["test"],
            "protected_by": _protected_by(name, formulas, declared_names),
        })

    flows_report = []
    for flow in sorted(live_flows, key=lambda f: str(f.get("id"))):
        flow_id = str(flow.get("id"))
        refs = _scan_references(flow_id)
        classification = classify_flow(flow, refs)
        summary[classification] += 1
        flows_report.append({
            "id": flow_id,
            "name": flow.get("name"),
            "object_type_id": flow.get("objectTypeId"),
            "is_enabled": bool(flow.get("isEnabled")),
            "classification": classification,
            "protected_by": "do_not_archive_flow_ids" if flow_id in DO_NOT_ARCHIVE_FLOW_IDS else None,
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "portal_id": portal_id,
        "surfaces_scanned": {
            "executable": sorted(str(p.relative_to(ROOT)) for p in _iter_executable_files()),
            "test": sorted(str(p.relative_to(ROOT)) for p in _iter_test_files()),
            "excluded": [".planning/**", "**/*.md"],
        },
        "properties": properties_report,
        "flows": flows_report,
        "summary": dict(summary),
    }


def _archive_property_live(object_type: str, name: str) -> int:
    # Copied call shape from scripts/rollback_property_migration.py:_archive_property_live.
    import requests
    from src.hubspot_client import BASE_URL, hs_headers
    r = requests.delete(f"{BASE_URL}/crm/v3/properties/{object_type}/{name}", headers=hs_headers(), timeout=30)
    return r.status_code


def archive_property(object_type: str, name: str, classification: str) -> dict:
    """Refuses anything not classified `uncontested_orphan` as its first statement. Then
    re-checks the do-not-archive set and the live calculationFormula substring set
    immediately before the DELETE -- an independent second gate at the point of mutation,
    because the failure mode if classification were wrong is silent portfolio-wide score
    corruption, not a clean API rejection. Writes the property's full live definition to
    the dated archive directory before the DELETE, so the definition survives in git
    regardless of HubSpot's retention window."""
    if classification != "uncontested_orphan":
        raise ValueError(
            f"refusing to archive {object_type}/{name}: classification={classification!r} "
            "-- only 'uncontested_orphan' may reach the archival path"
        )
    if name in DO_NOT_ARCHIVE_COMPANY_PROPERTIES:
        raise ValueError(f"refusing to archive {object_type}/{name}: in DO_NOT_ARCHIVE_COMPANY_PROPERTIES")

    live_props = _get_live_properties(object_type)
    formulas = _live_calculation_formulas(live_props)
    if any(_name_pattern(name).search(f) for f in formulas):
        raise ValueError(f"refusing to archive {object_type}/{name}: named in a live calculationFormula")

    live = next((p for p in live_props if p["name"] == name), None)
    if live is None:
        return {"archived": False, "reason": "already_absent"}
    if live.get("hubspotDefined"):
        raise ValueError(f"refusing to archive {object_type}/{name}: hubspotDefined=true")

    text = json.dumps(live, indent=2, sort_keys=True) + "\n"
    _assert_no_secrets(text)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    definition_path = ARCHIVE_DIR / f"{name}.json"
    definition_path.write_text(text)

    status = _archive_property_live(object_type, name)
    return {
        "archived": True,
        "http_status": status,
        "definition_path": str(definition_path.relative_to(ROOT)),
    }


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_ARCHIVE", "false").lower() == "true"
    return (not dry_run) and allow


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="Path to write the JSON candidate report to.")
    parser.add_argument("--archive", action="store_true",
                         help="Attempt the gated archival pass for every uncontested_orphan. "
                              "Requires DRY_RUN=false AND ALLOW_HUBSPOT_PROPERTY_ARCHIVE=true.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this "
              "live derivation.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    desired = yaml.safe_load(CONFIG_PATH.read_text())
    declared_names = {p["name"] for p in desired.get("companies", {}).get("properties", []) or []}

    live_companies = _get_live_properties("companies")
    live_flows = _get_live_flows()

    report = build_candidate_report(live_companies, live_flows, declared_names, os.getenv("HUBSPOT_PORTAL_ID"))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _write():
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        _assert_no_secrets(text)
        out_path.write_text(text)

    _write()
    print(f"wrote {out_path}")
    print(f"classification counts: {report['summary']}")

    if args.archive:
        uncontested = [p for p in report["properties"] if p["classification"] == "uncontested_orphan"]
        if not _writes_allowed():
            print("DRY_RUN=false AND ALLOW_HUBSPOT_PROPERTY_ARCHIVE=true are both required to "
                  "actually archive (two-key gate) -- printing what would archive only.")
            print(f"would archive: {[p['name'] for p in uncontested]}")
            return 0
        for p in uncontested:
            result = archive_property("companies", p["name"], p["classification"])
            p["archived"] = bool(result.get("archived"))
            p["archive_result"] = result
            print(f"archived {p['name']}: {result}")
        _write()

    return 0


if __name__ == "__main__":
    sys.exit(main())
