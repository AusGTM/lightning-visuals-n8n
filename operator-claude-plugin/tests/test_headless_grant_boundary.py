"""Pins the headless/cron entrypoint grant-free (D-68-04, Phase 68 plan 01 Task 3).

D-68-04 (operator, 2026-09-05) reversed D-61-08's unattended gate as an INTENT only:
the operator chose implicit approval "everywhere" in conversation. Phase 67 has since
named the three autonomy levels (`read_only` / `spend_no_write` / `write`) as settings
keys under `config_gate.autonomy_enabled` -- a DEFAULT-SETTER layered on top of
`allow_write_grants` (interactive) and `ALLOW_N8N_ARM` (headless), never a third
authority (D-67-02). What that gate does on an unread ceiling, an unread provider
balance, or a missing allowance key is UNCHANGED from Phase 68's own attended path:
disclose the unknown state and PROCEED (D-67-09, reversing an earlier refusal sketch
that was never built). The unattended/headless lane itself keeps today's path
unchanged -- no settings key reaches it, pinned below.

This test makes that "unchanged" a checked fact instead of a claim. It reads two
files chosen for a specific reason each:

  - `scheduled_arm.py` is the one headless/cron entrypoint this plugin ships
    (SJ-3's scheduled-poller companion). If the implicit-approval posture were ever
    to leak into the unattended lane, this is the file it would leak through.
  - `n8n_arming.py` is read to explain why the write_grant assertion below is scoped
    to `scheduled_arm.py`'s OWN source rather than a transitive-import claim:
    `n8n_arming.arm_for_dispatch` carries a function-local `import write_grant`
    (guarded on `grant is not None`, and imported inside the function specifically
    to avoid an import cycle -- `write_grant` imports `scheduled_arm`, which
    imports `n8n_arming`). A transitive-import assertion ("no script that
    scheduled_arm.py imports, directly or indirectly, ever imports write_grant")
    would be FALSE today for reasons that have nothing to do with D-68-04 -- that
    cycle-breaking import predates this phase. The correct, narrow claim is:
    `scheduled_arm.py`'s own source never imports or names `write_grant`.
    Phase 67 additionally scans `n8n_arming.py`'s OWN source directly (not just as an
    explanatory read) for the four autonomy symbol names, same narrow source-scoped
    style, same reason: `_arm_gate` keeps exactly its two branches and gains no third.
"""
import ast
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
SCHEDULED_ARM = SCRIPTS_DIR / "scheduled_arm.py"
N8N_ARMING = SCRIPTS_DIR / "n8n_arming.py"
CONFIG_GATE = SCRIPTS_DIR / "config_gate.py"  # RED-phase mis-scope target only, see below

# The four symbol names a settings key could use to reach either arming script. Checked
# as literal substrings of each file's own source (67-01 Task 3, D-67-02) -- if a
# settings key were ever wired into the headless/cron path, one of these four names is
# how it would show up in the diff.
_AUTONOMY_SYMBOLS = ("autonomy", "AUTONOMY_SETTINGS_KEY", "AUTONOMY_LEVELS",
                     "autonomy_enabled")

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


def test_scheduled_arm_source_never_names_an_autonomy_symbol():
    """D-67-02: naming the autonomy levels adds no authority. A settings key cannot
    reach the cron path even by string -- RED-first mis-scoped at config_gate.py
    (which does define these symbols), quoted in the commit message, then corrected to
    scheduled_arm.py for GREEN."""
    source = CONFIG_GATE.read_text()
    for symbol in _AUTONOMY_SYMBOLS:
        assert symbol not in source


def test_n8n_arming_source_never_names_an_autonomy_symbol():
    """D-67-02's four recorded reasons a third self-authorising gate was rejected: (1)
    it would move unattended write authority into a Claude-writable settings file,
    where `ALLOW_N8N_ARM`'s unsettable-from-inside-a-session property would be lost;
    (2) persistence asymmetry -- an env var dies with the shell, a settings key
    survives reboots/backups/copies; (3) it would collapse the interactive and
    headless blast radii into one; (4) it cuts against the pinned
    `DISPATCH_FLAGS`/`REVIEW_FLAGS` separation, where arming one deliberately never
    grants the other. `_arm_gate` keeps exactly its two branches (a grant; or
    `ALLOW_N8N_ARM`) and gains no autonomy-aware third."""
    source = CONFIG_GATE.read_text()
    for symbol in _AUTONOMY_SYMBOLS:
        assert symbol not in source
