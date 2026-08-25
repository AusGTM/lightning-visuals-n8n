# tests/test_expression_sandbox_safety.py
#
# Found LIVE 2026-08-25, execution 11934. "Lusha Enrich"'s jsonBody expression called
# `Object.prototype.hasOwnProperty.call(REVEAL_MAP, f)`. n8n's EXPRESSION sandbox refuses
# any `prototype` access — 'Cannot access "prototype" due to security concerns' — and the
# node's `onError: continueRegularOutput` turned that refusal into an ordinary-looking
# item. Every contact enrichment run since b7428af (2026-07-30, the Lusha v3 rewire) lost
# its Lusha result silently: no failed execution, no error field, just one provider
# quietly missing from the waterfall for eight weeks.
#
# The asymmetry is the trap and the reason this guard is a class-guard rather than a pin
# on one node: Code nodes run in a DIFFERENT sandbox where `Object.prototype` is fine, so
# `n8n/code/*.js` uses it in seven places and always has. Only `=`-prefixed expression
# strings are affected, and nothing in the build makes the distinction visible to a
# reader.
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLOUD_WORKFLOWS = sorted((ROOT / "n8n").glob("wf_*.json"))

# The identifiers n8n's expression sandbox refuses outright. `constructor` and `__proto__`
# are the same family — blocked for the same prototype-pollution reason — and would fail
# the same silent way.
FORBIDDEN_IN_EXPRESSIONS = ("prototype", "__proto__", "constructor")


def _expression_strings(node):
    """Every `=`-prefixed parameter value on a node, at any depth. An n8n expression is
    exactly a string parameter beginning with `=`; jsCode (Code nodes) never is, which is
    what keeps this guard off the Code-node sandbox."""
    found = []

    def walk(value, path):
        if isinstance(value, str):
            if value.startswith("="):
                found.append((path, value))
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(node.get("parameters", {}), "parameters")
    return found


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_no_expression_touches_a_sandbox_forbidden_identifier(path):
    workflow = json.loads(path.read_text())
    offenders = []
    for node in workflow["nodes"]:
        for param_path, expression in _expression_strings(node):
            for forbidden in FORBIDDEN_IN_EXPRESSIONS:
                if forbidden in expression:
                    offenders.append((node["name"], param_path, forbidden))
    assert not offenders, (
        "an n8n EXPRESSION references an identifier the expression sandbox refuses; the "
        "node will return 'Cannot access \"...\" due to security concerns' as ITEM DATA "
        "and, with onError: continueRegularOutput, that failure is invisible: "
        f"{offenders}"
    )


def test_the_guard_would_have_caught_the_bug_it_was_written_for():
    """Non-vacuity. A guard that passes because it inspects nothing is worse than none —
    this pins that the walker actually reaches a nested jsonBody expression."""
    node = {
        "name": "Lusha Enrich (pre-fix shape)",
        "parameters": {
            "options": {"timeout": 20000},
            "jsonBody": ("={{ missing.filter((f) => "
                         "Object.prototype.hasOwnProperty.call(REVEAL_MAP, f)) }}"),
        },
    }
    found = _expression_strings(node)
    assert [p for p, _ in found] == ["parameters.jsonBody"]
    assert any("prototype" in expression for _, expression in found)


def test_code_nodes_are_deliberately_out_of_scope():
    """`Object.prototype` in a CODE node is correct and used in seven modules. If this
    guard ever started reading jsCode it would fail them all, and the fix would be to
    weaken the guard — so the exclusion is pinned, not assumed."""
    node = {"name": "Some Code Node",
            "parameters": {"jsCode": "Object.prototype.hasOwnProperty.call(x, 'k')"}}
    assert _expression_strings(node) == []
