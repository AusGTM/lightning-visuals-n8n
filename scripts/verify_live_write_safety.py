#!/usr/bin/env python3
"""scripts/verify_live_write_safety.py

Phase 22 Plan 02 (T-22-06..10) — the read-back that closes the armed window.
`scripts/deploy_n8n_workflows.py`'s exit code proves a PUT request was accepted, never
that the live artifact is what was intended — the lesson Phase 19's BUG 26 taught this
repo at the cost of a whole phase's verification (deployment drift found only by an
independent re-read). This is that independent re-read, specialized to the write-safety
constants: it answers, for BOTH write-decision Code nodes at once, whether writes are
armed, what the allowlist actually contains live, and whether the create flag is still
disabled.

Imports the checked constant set from `scripts/deploy_n8n_workflows.py`'s
`_OVERLAY_FLAG_SPEC` rather than re-typing the four names — the overlay and its
read-back must never drift apart (tests/test_verify_live_write_safety.py pins this).
Imports `_base_url()`/`_n8n_headers()`/`_get_live_workflows()` from the same module
rather than re-implementing auth or URL assembly, same convention as
scripts/verify_live_lusha_urls.py.

Two expectations, exclusive:
  disarmed (default) — passes only when BOTH write-decision nodes carry BOTH write
    flags disabled ("false") AND BOTH allowlist constants empty (""). A single
    still-enabled flag or a single leftover allowlist value fails the check.
  armed --allowlist VALUE — passes only when record writes read enabled ("true") on
    both nodes, the create flag still reads disabled ("false") on both nodes, and the
    live allowlist (TEST_RECORD_IDS or TEST_RECORD_DOMAINS, whichever is non-empty)
    reads exactly VALUE on both nodes.

Prints only node names, constant names, and their parsed literal values — the node's
jsCode body is read (to extract those literals) but never printed in full, and no
credential value is ever constructed or printed here.

Usage:
    python scripts/verify_live_write_safety.py                       # disarmed (default)
    python scripts/verify_live_write_safety.py --expectation armed --allowlist 9604614548
    python scripts/verify_live_write_safety.py --json                # machine-readable verdict

Live-only utility, same convention as its siblings: when n8n credentials are absent,
prints a skip banner and exits 0 with zero HTTP calls. Lives in scripts/ with no
`test_` prefix, so pytest never collects it as a test module.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from deploy_n8n_workflows import (  # noqa: E402
    _base_url,
    _n8n_headers,
    _get_live_workflows,
    _OVERLAY_FLAG_SPEC,
)

ENRICHMENT_WORKFLOW_NAME = "LV Enrichment (Cloud template)"

# The two write-decision Code nodes, one per lane (contacts / companies) — both must
# agree, since a single-node check would miss a partial (half-disarmed) rewrite.
WRITE_DECISION_NODE_NAMES = ("Decide Action", "Decide Company Action")

# Never re-typed: the checked set IS the overlay's overlayable set, imported directly.
CHECKED_CONSTANTS = tuple(_OVERLAY_FLAG_SPEC.keys())
ALLOWLIST_CONSTANTS = ("TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")
# Everything else in the checked set is a write-enabling boolean. Derived, not re-typed,
# so a constant added to the overlay (ALLOW_HUBSPOT_REVIEW_WRITES was the fifth, Phase 30
# Plan 01) is read back the moment it exists — an armed flag this verifier does not know
# about would otherwise report a live artifact as "disarmed PASS", which is the exact
# false-success this read-back exists to prevent.
BOOLEAN_CONSTANTS = tuple(c for c in CHECKED_CONSTANTS if c not in ALLOWLIST_CONSTANTS)

EXPECTATIONS = ("disarmed", "armed")

# Anchored over the `const NAME = "value";` declaration form every _OVERLAY_FLAG_SPEC
# literal is rendered as (a quoted JS string, never a bare boolean) — mirrors the
# looser re-scan regex in deploy_n8n_workflows.enable_baked_flags(), narrowed here to
# only the four names this verifier tracks.
_CONST_RE = re.compile(r'const\s+(\w+)\s*=\s*"([^"]*)"\s*;')


def _has_n8n() -> bool:
    return bool(os.getenv("N8N_URL")) and bool(os.getenv("N8N_API_KEY"))


def _get_live_workflow_detail(workflow_id: str) -> dict:
    import requests
    r = requests.get(f"{_base_url()}/api/v1/workflows/{workflow_id}", headers=_n8n_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def _find_live_enrichment_workflow():
    """Matches on `name` (n8n assigns `id` server-side), same idiom as
    verify_live_lusha_urls.py — the list endpoint's entry is re-fetched by id for the
    full node detail this verifier needs."""
    workflows = _get_live_workflows()
    match = next((w for w in workflows if w.get("name") == ENRICHMENT_WORKFLOW_NAME), None)
    if match is None:
        return None
    return _get_live_workflow_detail(match["id"])


def _parse_constants(js_code: str) -> dict:
    """Extract the four write-safety constants' literal string values out of one node's
    jsCode. Only names in CHECKED_CONSTANTS are kept; anything else in the body (e.g.
    the taxonomy module's unrelated `const`s in Decide Company Action) is ignored."""
    found = {}
    for m in _CONST_RE.finditer(js_code or ""):
        name, value = m.group(1), m.group(2)
        if name in CHECKED_CONSTANTS:
            found[name] = value
    return found


def _node_report(workflow: dict, node_name: str) -> dict:
    """Never raises — a missing node or a node missing one of the four constants is an
    explicit reason in the report, not an exception."""
    node = next((n for n in (workflow.get("nodes") or []) if n.get("name") == node_name), None)
    if node is None:
        return {"name": node_name, "error": f"node {node_name!r} not found in the live workflow", "constants": {}}

    js_code = (node.get("parameters") or {}).get("jsCode") or ""
    constants = _parse_constants(js_code)
    missing = [c for c in CHECKED_CONSTANTS if c not in constants]
    if missing:
        return {
            "name": node_name,
            "error": f"node {node_name!r} is missing constant(s): {', '.join(missing)}",
            "constants": constants,
        }
    return {"name": node_name, "error": None, "constants": constants}


def verify(workflow: dict, expectation: str, expected_allowlist: str = None) -> dict:
    """Pure — takes an already-fetched workflow dict, returns a per-node report plus a
    pass/fail verdict. No network. Drives the entire offline test suite."""
    if expectation not in EXPECTATIONS:
        raise ValueError(f"unknown expectation {expectation!r}; must be one of {EXPECTATIONS}")
    if expectation == "armed" and not expected_allowlist:
        raise ValueError("the armed expectation requires a non-empty expected_allowlist")

    node_reports = [_node_report(workflow, name) for name in WRITE_DECISION_NODE_NAMES]
    reasons = []

    for report in node_reports:
        if report["error"]:
            reasons.append(report["error"])
            continue

        c = report["constants"]
        name = report["name"]

        if expectation == "disarmed":
            for flag in BOOLEAN_CONSTANTS:
                if c[flag] != "false":
                    reasons.append(f"{name}: {flag}={c[flag]!r}, expected \"false\"")
            for allow_const in ALLOWLIST_CONSTANTS:
                if c[allow_const] != "":
                    reasons.append(
                        f"{name}: {allow_const}={c[allow_const]!r}, expected empty (stale allowlist residue)"
                    )
        else:  # armed
            if c["ALLOW_HUBSPOT_RECORD_WRITES"] != "true":
                reasons.append(
                    f"{name}: ALLOW_HUBSPOT_RECORD_WRITES={c['ALLOW_HUBSPOT_RECORD_WRITES']!r}, expected \"true\""
                )
            # Every OTHER write-enabling boolean must still read disabled. The canary's
            # scope is record writes only — never create, and never review writeback,
            # which is a separate arming authority (D-02, Phase 30 Plan 01): a dispatch
            # armed window that also left review armed is a widened blast radius.
            for flag in BOOLEAN_CONSTANTS:
                if flag == "ALLOW_HUBSPOT_RECORD_WRITES" or c[flag] == "false":
                    continue
                reasons.append(
                    f"{name}: {flag}={c[flag]!r}, expected \"false\" "
                    f"(canary scope is record writes only)"
                )
            observed = c["TEST_RECORD_IDS"] or c["TEST_RECORD_DOMAINS"]
            if observed != expected_allowlist:
                reasons.append(
                    f"{name}: allowlist is TEST_RECORD_IDS={c['TEST_RECORD_IDS']!r} "
                    f"TEST_RECORD_DOMAINS={c['TEST_RECORD_DOMAINS']!r}, expected {expected_allowlist!r}"
                )

    return {
        "expectation": expectation,
        "expected_allowlist": expected_allowlist,
        "nodes": node_reports,
        "ok": not reasons,
        "reasons": reasons,
    }


def _print_report(result: dict) -> None:
    print(f"workflow: {ENRICHMENT_WORKFLOW_NAME!r}")
    print(f"expectation: {result['expectation']}")
    if result["expectation"] == "armed":
        print(f"expected allowlist: {result['expected_allowlist']!r}")

    for report in result["nodes"]:
        if report["error"]:
            print(f"node {report['name']!r}: ERROR — {report['error']}")
            continue
        c = report["constants"]
        # Every checked constant is printed, not a hardcoded four — an operator reading
        # this report must be able to see the state of a flag added after it was written.
        rendered = " ".join(f"{k}={c[k]!r}" for k in CHECKED_CONSTANTS)
        print(f"node {report['name']!r}: {rendered}")

    for reason in result["reasons"]:
        print(f"FAIL: {reason}")

    verdict = "PASS" if result["ok"] else "FAIL"
    print(f"VERDICT: {result['expectation']} {verdict}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--expectation", choices=EXPECTATIONS, default="disarmed",
                         help="which live state to check for (default: disarmed)")
    parser.add_argument("--allowlist", default=None,
                         help="expected allowlist value; required when --expectation=armed")
    parser.add_argument("--json", action="store_true", help="emit the verdict as one JSON object")
    args = parser.parse_args(argv)

    if args.expectation == "armed" and not args.allowlist:
        parser.error("--allowlist is required when --expectation=armed")

    if not _has_n8n():
        print("skipped (no n8n creds): the n8n URL and API key must both be set to run this verifier.")
        return 0

    workflow = _find_live_enrichment_workflow()
    if workflow is None:
        print(f"FAIL: no live workflow named {ENRICHMENT_WORKFLOW_NAME!r} was found.")
        return 1

    result = verify(workflow, args.expectation, args.allowlist)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_report(result)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
