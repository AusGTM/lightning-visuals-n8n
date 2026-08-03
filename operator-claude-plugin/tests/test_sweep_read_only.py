"""29-03 Task 2 — NOTICE-05's enforcement: the sweep has NO code path to a mutation.

Two independent assertions, allowlist-first (fails closed on anything new):

1. The transitive first-party import closure of `sweep_entry` is a subset of an explicit
   module allowlist. A new import fails until a human deliberately adds it — which is
   the moment someone has to think about whether the new module can write.
2. The only non-GET HTTP verb reachable anywhere in that closure is the single named
   exception: `backend_status.fetch_backend_status`'s POST to
   `webhook/hubspot/backend-status` (D-13). Every other write verb, module- or
   session-level, fails — so an allowlisted module that later grows a write is still
   caught.

WHY A POST IS A READ HERE (D-13, so the next reader does not re-derive it): the endpoint
is an n8n webhook and n8n webhooks answer on POST; the request carries no records and no
instruction — `json={}`, the empty literal — and its chain contains no write node, which
is a tested fact (test_backend_status_wiring.py::test_endpoint_chain_contains_no_write_node).
The exception is kept honest the same way test_retry_reuses_dispatch.py keeps its
send-shaped allowlist honest: the POST must carry no `files=`, no `data=`, and its
`json=` body must remain the empty dict literal, checked by AST so a reformat cannot
fool it. The moment it can carry records it is a send, and it loses the exemption.

Mirrors test_no_backend_imports.py's AST idiom — parse, never grep.
"""
import ast
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_ROOT / "scripts"

SWEEP_ENTRYPOINT = "sweep_entry"

# THE allowlist. Widening it is a deliberate act with a human attached.
#
# 29-05 Task 2 adds `execution_errors` (sweep_read's new gated get_execution +
# harvest_errors read for D-08b's swallowed-maintenance-failure detection, D-17).
# `error_table` was ALREADY present (imported by sweep_notify since 29-03); execution_errors
# imports it too, and it stays pure over already-fetched data either way — no write
# reaches this closure through it. Read both modules before adding them: neither performs
# I/O (execution_errors.harvest_errors walks an already-fetched execution payload;
# error_table.translate is a standard-library regex lookup), so this widening is the
# guard working as designed (D-10), not a regression.
ALLOWED_MODULES = {
    "sweep_entry", "sweep_read", "sweep_conditions", "sweep_notify",
    "config_gate", "n8n_read", "backend_status", "error_table", "execution_errors",
}

WRITE_VERBS = {"post", "put", "patch", "delete"}

# (module, verb) pairs permitted in the closure — exactly one (D-13).
ALLOWED_VERB_SITES = {("backend_status", "post")}


def _first_party_imports(path: Path, scripts_dir: Path):
    """Module names imported by `path` that resolve to files in scripts_dir."""
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        for name in names:
            top = name.split(".")[0]
            if (scripts_dir / f"{top}.py").exists():
                found.add(top)
    return found


def transitive_closure(entry: str, scripts_dir: Path):
    """Every first-party module reachable from `entry`, entry included."""
    seen, frontier = set(), {entry}
    while frontier:
        module = frontier.pop()
        if module in seen:
            continue
        seen.add(module)
        frontier |= _first_party_imports(scripts_dir / f"{module}.py", scripts_dir)
    return seen


def write_verb_sites(modules, scripts_dir: Path):
    """(module, verb) for every attribute access to an HTTP write verb in the given
    modules — `requests.post`, `session.put`, anything `.delete`-shaped."""
    sites = set()
    for module in modules:
        tree = ast.parse((scripts_dir / f"{module}.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in WRITE_VERBS:
                sites.add((module, node.attr))
    return sites


def status_post_payload_violations(path: Path):
    """AST check that fetch_backend_status's transport call stays bodyless: `json=`
    must be the empty dict literal, and no `files=` / `data=` may appear anywhere in
    the function. Returns human-readable violations; empty means honest."""
    tree = ast.parse(path.read_text())
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "fetch_backend_status":
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                for kw in call.keywords:
                    if kw.arg in ("files", "data"):
                        violations.append(f"carries {kw.arg}= — a payload channel")
                    if kw.arg == "json":
                        if not (isinstance(kw.value, ast.Dict) and not kw.value.keys):
                            violations.append("json= is not the empty dict literal")
            break
    else:
        violations.append("fetch_backend_status not found")
    return violations


# --- the two live assertions ------------------------------------------------------------

def test_the_sweep_import_closure_is_exactly_the_allowlist():
    closure = transitive_closure(SWEEP_ENTRYPOINT, SCRIPTS)
    assert closure <= ALLOWED_MODULES, (
        f"new module(s) in the sweep graph: {sorted(closure - ALLOWED_MODULES)} — "
        f"before widening ALLOWED_MODULES, decide whether they can write"
    )
    # And no stale allowlist fat: every allowed module is genuinely reachable, so the
    # list stays a description of the graph rather than a wish.
    assert closure == ALLOWED_MODULES, (
        f"allowlisted but unreachable: {sorted(ALLOWED_MODULES - closure)}"
    )


def test_the_only_reachable_write_verb_is_the_named_status_post():
    closure = transitive_closure(SWEEP_ENTRYPOINT, SCRIPTS)
    sites = write_verb_sites(closure, SCRIPTS)
    assert sites == ALLOWED_VERB_SITES, (
        f"write verbs beyond the D-13 exception: {sorted(sites - ALLOWED_VERB_SITES)}"
    )


def test_the_allowlisted_post_is_still_bodyless():
    assert status_post_payload_violations(SCRIPTS / "backend_status.py") == []


# --- proof the guard bites (synthetic modules, never edited production code) ------------

def _mini_graph(tmp_path, entry_source, **modules):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "entry.py").write_text(entry_source)
    for name, source in modules.items():
        (scripts / f"{name}.py").write_text(source)
    return scripts


def test_the_guard_flags_an_import_outside_the_allowlist(tmp_path):
    scripts = _mini_graph(tmp_path, "import helper\nimport dispatch\n",
                          helper="x = 1\n", dispatch="def dispatch():\n    pass\n")
    closure = transitive_closure("entry", scripts)
    assert not closure <= {"entry", "helper"}, "the guard failed to flag a new import"


def test_the_guard_flags_a_non_allowlisted_write_verb(tmp_path):
    scripts = _mini_graph(
        tmp_path,
        "import requests\n\ndef go(url):\n    return requests.put(url)\n")
    sites = write_verb_sites({"entry"}, scripts)
    assert sites == {("entry", "put")}, "the guard failed to see a write verb"
    assert not sites <= ALLOWED_VERB_SITES


def test_the_guard_flags_the_status_post_growing_a_body(tmp_path):
    mutated = (SCRIPTS / "backend_status.py").read_text().replace(
        "json={},", 'json={"records": "smuggled"},')
    assert mutated != (SCRIPTS / "backend_status.py").read_text()
    bad = tmp_path / "backend_status.py"
    bad.write_text(mutated)
    assert status_post_payload_violations(bad), (
        "the compensating assertion failed to catch a payload-carrying status POST"
    )
