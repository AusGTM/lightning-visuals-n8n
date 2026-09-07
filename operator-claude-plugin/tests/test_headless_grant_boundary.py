"""Pins the headless/cron entrypoint grant-free (D-68-04, Phase 68 plan 01 Task 3).

D-68-04 (operator, 2026-09-05) reverses D-61-08's unattended gate as an INTENT only:
the operator chose implicit approval "everywhere" in conversation, but the gate
itself -- the autonomy tiers, the `CEILING_UNKNOWN` fail-closed condition, and
`ALLOW_N8N_ARM` -- is Phase 67's to build, not this phase's. Until 67 ships, the
unattended/headless lane keeps today's path unchanged.

This test makes that "unchanged" a checked fact instead of a claim. It reads two
files chosen for a specific reason each:

  - `scheduled_arm.py` is the one headless/cron entrypoint this plugin ships
    (SJ-3's scheduled-poller companion). If the implicit-approval posture were ever
    to leak into the unattended lane, this is the file it would leak through.
  - `n8n_arming.py` is read only to explain why the assertion below is scoped to
    `scheduled_arm.py`'s OWN source rather than a transitive-import claim:
    `n8n_arming.arm_for_dispatch` carries a function-local `import write_grant`
    (guarded on `grant is not None`, and imported inside the function specifically
    to avoid an import cycle -- `write_grant` imports `scheduled_arm`, which
    imports `n8n_arming`). A transitive-import assertion ("no script that
    scheduled_arm.py imports, directly or indirectly, ever imports write_grant")
    would be FALSE today for reasons that have nothing to do with D-68-04 -- that
    cycle-breaking import predates this phase. The correct, narrow claim is:
    `scheduled_arm.py`'s own source never imports or names `write_grant`.
"""
import ast
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SCHEDULED_ARM = SCRIPTS_DIR / "scheduled_arm.py"

# The one file allowed to define/call plan_grant/open_grant — grant opening is a
# conversation-time act (backend-control/SKILL.md's "Opening a write grant"), never
# something a headless entrypoint reaches directly.
_GRANT_OPENING_HOME = "write_grant.py"


def _imported_names(tree):
    """Every module name this file's own AST imports — `import X` and `from X
    import ...` alike — mirroring test_report_sufficiency.py's `_imports_forbidden_module`
    walk style."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def test_scheduled_arm_does_not_import_write_grant():
    tree = ast.parse(SCHEDULED_ARM.read_text(), filename=str(SCHEDULED_ARM))
    assert "write_grant" not in _imported_names(tree)


def test_scheduled_arm_source_never_names_write_grant():
    # Source-scoped, not transitive (see module docstring) — `n8n_arming.py`'s
    # function-local `import write_grant` inside `arm_for_dispatch` is real and
    # pre-existing; it must not make this file's own text mention the module.
    source = SCHEDULED_ARM.read_text()
    assert "write_grant" not in source


def test_only_write_grant_module_calls_grant_opening_functions():
    offenders = []
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        if path.name == _GRANT_OPENING_HOME:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
                if name in ("plan_grant", "open_grant"):
                    offenders.append(f"{path.name}: calls {name}()")
    assert not offenders, (
        "D-68-04: grant opening is a conversation-time act documented in SKILL.md, "
        f"never reachable from a headless entrypoint. Offenders: {offenders}"
    )
