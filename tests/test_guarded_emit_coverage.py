# tests/test_guarded_emit_coverage.py
#
# Phase 50 security audit, 2026-09-03 — T-50-11 / T-50-27 / T-50-36.
#
# Three threat-register entries asserted that `assert_no_secrets` was applied to the
# artifacts five scripts write. It never had been. Not drift — NEVER PRESENT, on paths
# whose registers claimed the guard for the life of the phase. Nothing would ever have
# caught it, because nothing was checking that the guard had a caller.
#
# That is what this file is for. It does not test the guard (src/guards.py's own tests
# do); it tests that the guard is REACHED. A guard with no call site is documentation.

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# The five scripts the audit found unguarded, now routed through src.guards' wrappers.
# A script joins this list when it serializes anything to a committed artifact — a file
# under .planning/ or config/, or stdout that a run record captures.
GUARDED_EMIT_SCRIPTS = (
    "check_tier_derived_parity.py",
    "apply_fit_score_formula.py",
    "rollback_property_migration.py",
    "put_hubspot_flow.py",
    "backfill_anti_icp_flag_num.py",
)

# The guarded paths. Anything emitting a committed artifact goes through one of these,
# or through a module-local `_assert_no_secrets` wrapper (the older convention, still
# used by the seven scripts that already had the guard before this audit).
GUARDED_NAMES = frozenset({"emit_json", "write_guarded", "assert_no_secrets",
                           "_assert_no_secrets"})

# Raw emit calls that must never appear un-guarded in the scripts above.
RAW_PRINT_JSON = ("print", "json.dumps")


def _tree(name):
    return ast.parse((ROOT / "scripts" / name).read_text()), name


@pytest.mark.parametrize("script", GUARDED_EMIT_SCRIPTS)
def test_script_imports_a_guarded_emit_path(script):
    """Every audited script must import at least one guarded emitter.

    An import is the cheapest thing to check and the first thing to disappear in the
    failure this test exists to prevent — the five scripts did not merely fail to call
    the guard, they never imported it.
    """
    tree, name = _tree(script)
    imported = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("src.guards")
        for alias in node.names
    }
    assert imported & GUARDED_NAMES, (
        f"{name} imports no guarded emitter from src.guards. Its committed artifacts "
        f"would reach disk or stdout unscanned — the exact T-50-11/27/36 shape."
    )


@pytest.mark.parametrize("script", GUARDED_EMIT_SCRIPTS)
def test_script_makes_no_raw_print_json_dumps_call(script):
    """`print(json.dumps(...))` is the unguarded stdout path — it must not survive.

    stdout matters as much as a file: these scripts' output is routinely captured into a
    committed run record, so a token reaching stdout reaches git.
    """
    tree, name = _tree(script)
    offenders = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == RAW_PRINT_JSON[0]):
            continue
        for arg in node.args:
            if (isinstance(arg, ast.Call)
                    and isinstance(arg.func, ast.Attribute)
                    and arg.func.attr == "dumps"):
                offenders.append(getattr(node, "lineno", "?"))
    assert not offenders, (
        f"{name} calls print(json.dumps(...)) unguarded at line(s) {offenders}. "
        f"Use src.guards.emit_json, which serializes, scans and prints in one call."
    )


@pytest.mark.parametrize("script", GUARDED_EMIT_SCRIPTS)
def test_script_makes_no_bare_write_text_call(script):
    """`.write_text(...)` on any path is the unguarded file path.

    `src.guards.write_guarded` scans BEFORE writing, so a leak raises with nothing on
    disk rather than leaving a poisoned artifact for the caller to clean up.
    """
    tree, name = _tree(script)
    offenders = [
        getattr(node, "lineno", "?")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "write_text"
    ]
    assert not offenders, (
        f"{name} calls .write_text(...) directly at line(s) {offenders}. "
        f"Use src.guards.write_guarded, which scans before the write."
    )


def test_the_guard_actually_raises_on_each_leak_shape():
    """The wrappers are only worth pinning if what they wrap has teeth.

    Without this, the three tests above could pass against a guard that had been quietly
    hollowed out — which is the same class of failure in a different place.
    """
    from src.guards import assert_no_secrets

    for leak in ('{"headers": {"Authorization": "Bearer x"}}',
                 '{"env": "HUBSPOT_PRIVATE_APP_TOKEN"}'):
        with pytest.raises(ValueError):
            assert_no_secrets(leak)

    assert_no_secrets('{"company": "Australian Turf Club", "tier": "B"}')  # must not raise


def test_write_guarded_leaves_nothing_on_disk_when_it_refuses(tmp_path):
    """The check runs before the write, not after — proven, not assumed."""
    from src.guards import write_guarded

    target = tmp_path / "artifact.json"
    with pytest.raises(ValueError):
        write_guarded(target, '{"Authorization": "Bearer leaked"}')
    assert not target.exists(), "write_guarded wrote a poisoned artifact before refusing"

    write_guarded(target, '{"ok": true}')
    assert target.read_text() == '{"ok": true}'
