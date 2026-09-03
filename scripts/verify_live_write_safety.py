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

Phase 60 Plan 05 (G-60-2, 2026-09-03) ADDENDUM: `--armed-workflow NAME` lets an operator
pin a correctly-scoped SINGLE-workflow armed window — the exact shape `armed_review_window`
arms (one workflow), which the global armed model above could not express: a flag declared
by nodes in four workflows but armed by the code in only one made every OTHER workflow's
correctly-disarmed node report a FAIL, which is what the 2026-09-03 live walk hit. This is
NOT the workflow-selection flag D-07 refused, for three reasons that together keep D-07's
guarantee intact: (1) coverage is unchanged — every deployed workflow is still fetched and
every declaring node in it is still judged, none is skipped; (2) the workflows that are NOT
named are held to the DISARMED rule under an armed expectation — STRICTER than the global
armed rule they were held to before, which never checked their allowlist constants for
residue; (3) a name matching zero scanned workflows is a hard FAIL naming the value given
and the workflow names that were actually scanned, so a typo can never narrow the scan into
a silent pass. Omitting the argument reproduces today's unscoped verdict exactly.

Imports the checked constant set from `scripts/deploy_n8n_workflows.py`'s
`_OVERLAY_FLAG_SPEC` rather than re-typing the names — the overlay and its read-back must
never drift apart (tests/test_verify_live_write_safety.py pins this). Imports
`_base_url()`/`_n8n_headers()`/`_get_live_workflows()` from the same module rather than
re-implementing auth or URL assembly, same convention as scripts/verify_live_lusha_urls.py.

Two expectations, exclusive:
  disarmed (default) — passes only when EVERY declaring node reads every write-enabling
    boolean it declares as "false" AND every allowlist constant it declares as "". A
    single still-enabled flag or a single leftover allowlist value anywhere fails.
  armed --allowlist VALUE [--expect-armed FLAG,FLAG] — symmetric: the named flags must
    read enabled wherever they are declared, EVERY other write-enabling boolean must still
    read disabled wherever it is declared, and the live allowlist (TEST_RECORD_IDS or
    TEST_RECORD_DOMAINS, whichever is non-empty) must read exactly VALUE. Naming a flag
    narrows nothing else. Omitting --expect-armed means record writes alone, which is
    exactly what this script has always meant — an operator who forgets the argument gets
    the STRICTER verdict, never a permissive one.

An armed window whose allowlist reads empty is its own finding, not a pass:
`_writeSafetyAllows()` returns false on an empty allowlist, so that state grants nothing
while every flag reads enabled.

Phase 44 Plan 01: `ALLOW_SJ3_DRAIN_WRITES` (rests "true", D-05) is checked separately
under both expectations with the OPPOSITE polarity — it must be present and read "true",
or the SJ-3 drain is silently inert and the stuck queue can re-form. It is deliberately
not in CHECKED_CONSTANTS (see the comment at its definition below) and gets its own
report line; the five overlay constants' verdict keeps its meaning unchanged.

A scan that discovers ZERO declaring nodes is a failure with an explicit reason, never a
disarmed pass: a scan that matched nothing is otherwise indistinguishable from a disarmed
instance.

Prints only workflow names, node names, constant names and their parsed literal values —
the node's jsCode body is read (to extract those literals) but never printed in full, and
no credential value is ever constructed or printed here.

Usage:
    python scripts/verify_live_write_safety.py                       # disarmed (default)
    python scripts/verify_live_write_safety.py --expectation armed --allowlist 9604614548
    python scripts/verify_live_write_safety.py --expectation armed --allowlist australiagtm.com \
        --expect-armed ALLOW_HUBSPOT_RECORD_WRITES,ALLOW_HUBSPOT_CREATE
    python scripts/verify_live_write_safety.py --expectation armed --allowlist 9604738976 \
        --expect-armed ALLOW_HUBSPOT_REVIEW_WRITES --armed-workflow "LV Review Decision (Cloud)"
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

# Phase 44 Plan 01 (D-05, T-44-05) — the SJ-3 drain authority is deliberately OUTSIDE
# CHECKED_CONSTANTS: it rests "true", and the disarmed branch below hard-requires every
# boolean it tracks to read "false", so folding it in would declare a correctly-disarmed
# backend armed. It is checked SEPARATELY, with the opposite polarity, in every
# expectation: the constant must be present in the live workflow content and read
# "true" — a missing or "false" ALLOW_SJ3_DRAIN_WRITES means the drain is silently inert
# and the stuck queue can re-form, the exact failure Phase 44 exists to prevent. It gets
# its own report line and its own reasons; the armed/disarmed verdict for the five
# overlay constants keeps its meaning unchanged.
DRAIN_CONSTANT = "ALLOW_SJ3_DRAIN_WRITES"
DRAIN_EXPECTED = "true"
ALLOWLIST_CONSTANTS = ("TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")
# Everything else in the checked set is a write-enabling boolean. Derived, not re-typed,
# so a constant added to the overlay (ALLOW_HUBSPOT_REVIEW_WRITES was the fifth, Phase 30
# Plan 01) is read back the moment it exists — an armed flag this verifier does not know
# about would otherwise report a live artifact as "disarmed PASS", which is the exact
# false-success this read-back exists to prevent.
BOOLEAN_CONSTANTS = tuple(c for c in CHECKED_CONSTANTS if c not in ALLOWLIST_CONSTANTS)

# What `--expectation armed` meant before an expected-armed set existed (Phase 22). Kept
# as the default so every pre-23-07 call site — including the completed Phase 22 runbook's
# command lines — keeps its exact meaning and still fails closed.
DEFAULT_EXPECT_ARMED = ("ALLOW_HUBSPOT_RECORD_WRITES",)

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
    jsCode. Only names in CHECKED_CONSTANTS (plus DRAIN_CONSTANT, checked separately)
    are kept; anything else in the body (e.g. the taxonomy module's unrelated `const`s
    in Decide Company Action) is ignored."""
    found = {}
    for m in _CONST_RE.finditer(js_code or ""):
        name, value = m.group(1), m.group(2)
        if name in CHECKED_CONSTANTS or name == DRAIN_CONSTANT:
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


def _resolve_expect_armed(expected_armed) -> tuple:
    """`None` means the caller said nothing and gets Phase 22's meaning; an explicitly
    empty collection is a mistake, not a request to expect nothing."""
    if expected_armed is None:
        return DEFAULT_EXPECT_ARMED
    names = tuple(expected_armed)
    if not names:
        raise ValueError(
            "the armed expectation requires at least one expected-armed flag; "
            f"must be one or more of {BOOLEAN_CONSTANTS}"
        )
    unknown = [n for n in names if n not in BOOLEAN_CONSTANTS]
    if unknown:
        raise ValueError(
            f"unknown expected-armed flag(s): {', '.join(repr(n) for n in unknown)}; "
            f"must be one or more of {BOOLEAN_CONSTANTS}"
        )
    return names


def _judge_disarmed_report(report: dict, reasons: list) -> None:
    """Every write-enabling boolean this node declares must read \"false\", and every
    allowlist constant it declares must read empty. Pure list-mutating helper so the exact
    same rule body serves both the top-level `disarmed` expectation and a scoped `armed`
    expectation's judgment of every workflow that is NOT the one named armed."""
    c = report["constants"]
    where = f"{report['workflow']} / {report['node']}"
    for flag in BOOLEAN_CONSTANTS:
        if flag in c and c[flag] != "false":
            reasons.append(f"{where}: {flag}={c[flag]!r}, expected \"false\"")
    for allow_const in ALLOWLIST_CONSTANTS:
        if allow_const in c and c[allow_const] != "":
            reasons.append(
                f"{where}: {allow_const}={c[allow_const]!r}, expected empty (stale allowlist residue)"
            )


def _judge_armed_report(report: dict, reasons: list, armed_flags: tuple, expected_allowlist: str) -> None:
    """The named flags must read \"true\" wherever declared; every OTHER write-enabling
    boolean this node declares must still read \"false\"; the live allowlist must read
    exactly `expected_allowlist`. The rule body for the workflow that IS named armed (or,
    under the unscoped/global form, every workflow — unchanged since Phase 22)."""
    c = report["constants"]
    where = f"{report['workflow']} / {report['node']}"
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


def verify(workflows, expectation: str, expected_allowlist: str = None, expected_armed=None,
           armed_workflow: str = None) -> dict:
    """Pure — takes a LIST of already-fetched workflow dicts, returns a per-workflow
    per-node report plus a pass/fail verdict. No network. Drives the entire offline suite.

    The armed expectation is symmetric: naming a flag says it must read enabled, and says
    nothing else — every write-enabling boolean NOT named is still asserted disabled, in
    every declaring node of every workflow.

    `armed_workflow` (G-60-2, Phase 60 Plan 05), armed expectation only, defaults to
    `None`: when `None`, every code path below behaves exactly as it always has — the armed
    rule applies to every declaring node of every workflow, unscoped. When given, it names
    the ONE workflow expected armed: that workflow's own declaring nodes are judged by the
    armed rule above; every OTHER workflow's declaring nodes are judged by the DISARMED rule
    instead — stricter than the unscoped armed rule, which only required their OTHER
    booleans read \"false\" and never checked their allowlist constants for residue. Naming
    a workflow that matches none of the ones scanned is itself a hard failure (see below);
    coverage is never narrowed — every workflow is still fetched and every declaring node in
    it is still judged, whichever rule it is judged by."""
    if expectation not in EXPECTATIONS:
        raise ValueError(f"unknown expectation {expectation!r}; must be one of {EXPECTATIONS}")

    armed_flags = ()
    if expectation == "armed":
        if not expected_allowlist:
            raise ValueError("the armed expectation requires a non-empty expected_allowlist")
        armed_flags = _resolve_expect_armed(expected_armed)

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

    scoped = expectation == "armed" and armed_workflow is not None
    if scoped:
        scanned_names = [wf["name"] for wf in grouped]
        if armed_workflow not in scanned_names:
            reasons.append(
                f"no scanned workflow matches the named armed workflow {armed_workflow!r}; "
                f"workflows scanned: {', '.join(scanned_names) or '(none)'}. A name matching "
                "nothing is a hard failure, never a quiet pass."
            )

    for report in reports:
        if expectation == "disarmed":
            _judge_disarmed_report(report, reasons)
        elif scoped and report["workflow"] != armed_workflow:
            _judge_disarmed_report(report, reasons)
        else:
            _judge_armed_report(report, reasons, armed_flags, expected_allowlist)

    # Phase 44 Plan 01 (T-44-05) — the drain authority's dedicated check, opposite
    # polarity to everything above and applied under BOTH expectations: present and
    # "true", or the SJ-3 drain is silently inert and the queue can re-form. Its reasons
    # join the verdict (a silent drain is a failure), but the five overlay constants'
    # armed/disarmed meaning above is untouched.
    drain_declaring = [r for r in reports if DRAIN_CONSTANT in r["constants"]]
    drain_reasons = []
    for report in drain_declaring:
        value = report["constants"][DRAIN_CONSTANT]
        if value != DRAIN_EXPECTED:
            drain_reasons.append(
                f"{report['workflow']} / {report['node']}: {DRAIN_CONSTANT}={value!r}, expected "
                f"\"{DRAIN_EXPECTED}\" — the SJ-3 drain is silently inert and the stuck queue can re-form"
            )
    if reports and not drain_declaring:
        drain_reasons.append(
            f"{DRAIN_CONSTANT} is declared by no node in any deployed workflow — the SJ-3 "
            "drain is silently inert and the stuck queue can re-form (Phase 44 Plan 01)"
        )
    reasons.extend(drain_reasons)

    return {
        "expectation": expectation,
        "expected_allowlist": expected_allowlist,
        "expected_armed": list(armed_flags),
        "armed_workflow": armed_workflow,
        "workflows_scanned": len(workflows),
        "declaring_nodes": len(reports),
        "workflows": grouped,
        "drain": {
            "constant": DRAIN_CONSTANT,
            "expected": DRAIN_EXPECTED,
            "declaring_nodes": len(drain_declaring),
            "ok": not drain_reasons,
        },
        "ok": not reasons,
        "reasons": reasons,
    }


def _print_report(result: dict) -> None:
    print(f"expectation: {result['expectation']}")
    if result["expectation"] == "armed":
        print(f"expected allowlist: {result['expected_allowlist']!r}")
        print(f"expected armed: {', '.join(result['expected_armed'])}")
        if result.get("armed_workflow"):
            print(
                f"armed workflow: {result['armed_workflow']!r} — every OTHER workflow is "
                "asserted fully disarmed"
            )
        else:
            print("every other write-enabling boolean is asserted disabled wherever it is declared")
    print(
        f"coverage: {result['workflows_scanned']} workflow(s) fetched, "
        f"{result['declaring_nodes']} declaring node(s) found"
    )
    # Phase 44 Plan 01 — the drain authority's own line, never folded into the
    # armed/disarmed verdict: missing or "false" means the SJ-3 drain is silently inert.
    drain = result.get("drain") or {}
    drain_verdict = "PASS" if drain.get("ok") else "FAIL"
    print(
        f"drain authority: {drain.get('constant', DRAIN_CONSTANT)} expected "
        f"\"{drain.get('expected', DRAIN_EXPECTED)}\", declared by "
        f"{drain.get('declaring_nodes', 0)} node(s) — {drain_verdict}"
    )

    for wf in result["workflows"]:
        if not wf["nodes"]:
            continue
        print(f"workflow {wf['name']!r}:")
        for report in wf["nodes"]:
            c = report["constants"]
            # Only the constants THIS node declares — a partial declaration is the real
            # committed shape, not a defect, and printing a phantom value would misread.
            rendered = " ".join(
                f"{k}={c[k]!r}" for k in CHECKED_CONSTANTS + (DRAIN_CONSTANT,) if k in c)
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
    parser.add_argument("--expect-armed", default=None,
                         help="comma-separated write-enabling flags expected ENABLED, same shape as "
                              "ENABLE_BAKED_FLAGS. Every flag NOT named is still asserted disabled. "
                              "Armed expectation only; defaults to ALLOW_HUBSPOT_RECORD_WRITES")
    parser.add_argument("--armed-workflow", default=None,
                         help="the ONE workflow name expected armed (G-60-2); every OTHER deployed "
                              "workflow is asserted fully disarmed, stricter than the unscoped armed "
                              "rule. A name matching no scanned workflow is a hard failure. Armed "
                              "expectation only; omitting it keeps today's unscoped meaning")
    parser.add_argument("--json", action="store_true", help="emit the verdict as one JSON object")
    args = parser.parse_args(argv)

    if args.expectation == "armed" and not args.allowlist:
        parser.error("--allowlist is required when --expectation=armed")
    if args.expectation != "armed" and args.expect_armed:
        parser.error("--expect-armed is only meaningful with --expectation=armed")
    if args.expectation != "armed" and args.armed_workflow:
        parser.error("--armed-workflow is only meaningful with --expectation=armed")

    expected_armed = None
    if args.expect_armed:
        expected_armed = [f.strip() for f in args.expect_armed.split(",") if f.strip()]
        # Validated BEFORE the credentials check, so a typo can never silently expect
        # nothing and never spends a live request first.
        try:
            _resolve_expect_armed(expected_armed)
        except ValueError as exc:
            parser.error(str(exc))

    if not _has_n8n():
        print("skipped (no n8n creds): the n8n URL and API key must both be set to run this verifier.")
        return 0

    result = verify(_fetch_all_live_workflows(), args.expectation, args.allowlist, expected_armed,
                     args.armed_workflow)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_report(result)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
