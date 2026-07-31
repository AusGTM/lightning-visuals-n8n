#!/usr/bin/env python3
"""scripts/verify_live_write_safety.py

Phase 22 Plan 02 (T-22-06..10) — the read-back that closes the armed window.
`scripts/deploy_n8n_workflows.py`'s exit code proves a PUT request was accepted, never
that the live artifact is what was intended — the lesson Phase 19's BUG 26 taught this
repo at the cost of a whole phase's verification (deployment drift found only by an
independent re-read). This is that independent re-read, specialized to the write-safety
constants: it answers, for EVERY node in EVERY deployed workflow that declares one,
whether writes are armed, what the allowlist actually contains live, and which flags are
still disabled.

Phase 23 Plan 07 (D-19) — coverage is DISCOVERED, never listed. The previous version
named one workflow and two nodes, so it inspected 2 of the 11 declaring nodes and no node
at all in the contact lane: its `disarmed PASS` was not evidence that lane was disarmed.
There is deliberately no workflow-selection argument (27-04's D-07 reasoning): the moment
an operator can narrow the scan the read-back can go blind again, and a workflow deployed
or renamed later must show up without anyone editing this file.

Imports the checked constant set from `scripts/deploy_n8n_workflows.py`'s
`_OVERLAY_FLAG_SPEC` rather than re-typing the names — the overlay and its read-back must
never drift apart (tests/test_verify_live_write_safety.py pins this). Imports
`_base_url()`/`_n8n_headers()`/`_get_live_workflows()` from the same module rather than
re-implementing auth or URL assembly, same convention as scripts/verify_live_lusha_urls.py.

Two expectations, exclusive:
  disarmed (default) — passes only when EVERY declaring node reads every write-enabling
    boolean it declares as "false" AND every allowlist constant it declares as "". A
    single still-enabled flag or a single leftover allowlist value anywhere fails.
  armed --allowlist VALUE — passes only when record writes read enabled ("true") wherever
    declared, every other write-enabling boolean still reads disabled ("false") wherever
    declared, and the live allowlist (TEST_RECORD_IDS or TEST_RECORD_DOMAINS, whichever is
    non-empty) reads exactly VALUE.

A scan that discovers ZERO declaring nodes is a failure with an explicit reason, never a
disarmed pass: a scan that matched nothing is otherwise indistinguishable from a disarmed
instance.

Prints only workflow names, node names, constant names and their parsed literal values —
the node's jsCode body is read (to extract those literals) but never printed in full, and
no credential value is ever constructed or printed here.

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
# only the names this verifier tracks.
_CONST_RE = re.compile(r'const\s+(\w+)\s*=\s*"([^"]*)"\s*;')


def _has_n8n() -> bool:
    return bool(os.getenv("N8N_URL")) and bool(os.getenv("N8N_API_KEY"))


def _get_live_workflow_detail(workflow_id: str) -> dict:
    import requests
    r = requests.get(f"{_base_url()}/api/v1/workflows/{workflow_id}", headers=_n8n_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def _fetch_all_live_workflows() -> list:
    """Every deployed workflow, each re-fetched by id for the node detail the list
    endpoint omits. No name matching and no filter argument: what is deployed is what is
    scanned, so a workflow added or renamed later needs no code edit here."""
    return [_get_live_workflow_detail(w["id"]) for w in _get_live_workflows() if w.get("id")]


def _parse_constants(js_code: str) -> dict:
    """Extract the write-safety constants' literal string values out of one node's
    jsCode. Only names in CHECKED_CONSTANTS are kept; anything else in the body (e.g.
    the taxonomy module's unrelated `const`s in Decide Company Action) is ignored."""
    found = {}
    for m in _CONST_RE.finditer(js_code or ""):
        name, value = m.group(1), m.group(2)
        if name in CHECKED_CONSTANTS:
            found[name] = value
    return found


def _declaring_nodes(workflow: dict) -> list:
    """Pure. One entry per node whose parsed constants are non-empty — a node declaring
    none is skipped silently, and a workflow with no such node contributes nothing and is
    not an error. A node declaring a SUBSET is carried with exactly that subset: the
    contact lane's `Decide Action` declares only the create flag (23-01), and judging it
    against all five would report a legitimate node as broken on every run."""
    wf_name = workflow.get("name") or "<unnamed workflow>"
    reports = []
    for node in workflow.get("nodes") or []:
        constants = _parse_constants((node.get("parameters") or {}).get("jsCode") or "")
        if constants:
            reports.append({
                "workflow": wf_name,
                "node": node.get("name") or "<unnamed node>",
                "constants": constants,
            })
    return reports


def verify(workflows, expectation: str, expected_allowlist: str = None) -> dict:
    """Pure — takes a LIST of already-fetched workflow dicts, returns a per-workflow
    per-node report plus a pass/fail verdict. No network. Drives the entire offline suite."""
    if expectation not in EXPECTATIONS:
        raise ValueError(f"unknown expectation {expectation!r}; must be one of {EXPECTATIONS}")

    armed_flags = ()
    if expectation == "armed":
        if not expected_allowlist:
            raise ValueError("the armed expectation requires a non-empty expected_allowlist")
        armed_flags = ("ALLOW_HUBSPOT_RECORD_WRITES",)

    grouped = [
        {"name": wf.get("name") or "<unnamed workflow>", "nodes": _declaring_nodes(wf)}
        for wf in workflows
    ]
    reports = [n for wf in grouped for n in wf["nodes"]]
    reasons = []

    if not reports:
        reasons.append(
            f"zero declaring nodes found across {len(workflows)} fetched workflow(s): no node "
            f"declares any of {', '.join(CHECKED_CONSTANTS)}. A scan that matched nothing is not "
            "evidence of a disarmed instance — check credentials, tenant and deploy state."
        )

    for report in reports:
        c = report["constants"]
        where = f"{report['workflow']} / {report['node']}"

        if expectation == "disarmed":
            for flag in BOOLEAN_CONSTANTS:
                if flag in c and c[flag] != "false":
                    reasons.append(f"{where}: {flag}={c[flag]!r}, expected \"false\"")
            for allow_const in ALLOWLIST_CONSTANTS:
                if allow_const in c and c[allow_const] != "":
                    reasons.append(
                        f"{where}: {allow_const}={c[allow_const]!r}, expected empty (stale allowlist residue)"
                    )
            continue

        # armed
        for flag in BOOLEAN_CONSTANTS:
            if flag not in c:
                continue
            if flag in armed_flags:
                if c[flag] != "true":
                    reasons.append(
                        f"{where}: {flag}={c[flag]!r}, expected \"true\" (named in the expected-armed set)"
                    )
            elif c[flag] != "false":
                reasons.append(
                    f"{where}: {flag}={c[flag]!r}, expected \"false\" "
                    f"(armed scope is exactly {', '.join(armed_flags)})"
                )

        declared_allowlists = [a for a in ALLOWLIST_CONSTANTS if a in c]
        if declared_allowlists:
            observed = next((c[a] for a in ALLOWLIST_CONSTANTS if c.get(a)), "")
            if not observed:
                reasons.append(
                    f"{where}: every declared allowlist constant is empty "
                    f"({', '.join(f'{a}={c[a]!r}' for a in declared_allowlists)}), expected "
                    f"{expected_allowlist!r} — an empty allowlist grants NOTHING "
                    "(_writeSafetyAllows returns false), so this is not an armed window"
                )
            elif observed != expected_allowlist:
                reasons.append(
                    f"{where}: allowlist is "
                    f"{' '.join(f'{a}={c[a]!r}' for a in declared_allowlists)}, "
                    f"expected {expected_allowlist!r}"
                )

    return {
        "expectation": expectation,
        "expected_allowlist": expected_allowlist,
        "expected_armed": list(armed_flags),
        "workflows_scanned": len(workflows),
        "declaring_nodes": len(reports),
        "workflows": grouped,
        "ok": not reasons,
        "reasons": reasons,
    }


def _print_report(result: dict) -> None:
    print(f"expectation: {result['expectation']}")
    if result["expectation"] == "armed":
        print(f"expected allowlist: {result['expected_allowlist']!r}")
        print(f"expected armed: {', '.join(result['expected_armed'])}")
    print(
        f"coverage: {result['workflows_scanned']} workflow(s) fetched, "
        f"{result['declaring_nodes']} declaring node(s) found"
    )

    for wf in result["workflows"]:
        if not wf["nodes"]:
            continue
        print(f"workflow {wf['name']!r}:")
        for report in wf["nodes"]:
            c = report["constants"]
            # Only the constants THIS node declares — a partial declaration is the real
            # committed shape, not a defect, and printing a phantom value would misread.
            rendered = " ".join(f"{k}={c[k]!r}" for k in CHECKED_CONSTANTS if k in c)
            print(f"  node {report['node']!r}: {rendered}")

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

    result = verify(_fetch_all_live_workflows(), args.expectation, args.allowlist)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_report(result)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
