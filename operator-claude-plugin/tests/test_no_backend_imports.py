"""Architecture guard: the client touches no backend code (PLUGIN-04).

Mirrors tests/test_architecture_guard.py's guard-as-test idiom for a different
property: this repo's guard keeps n8n workflows middleware-free; this one keeps
operator-claude-plugin from forking the backend it's a thin client for. Parses with
`ast` rather than grepping, so a string mentioning a module name in a docstring cannot
fail the guard and an aliased import cannot slip past it.
"""
import ast
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

# The repo's own top-level packages this plugin must never import (D-01, PLUGIN-04) —
# not this plugin's own scripts/ directory, which is a different, flat-imported thing.
FORBIDDEN_TOP_LEVEL_PACKAGES = {"src", "scripts"}

# Named backend modules that would fork enrichment/scoring logic even if imported some
# other way (e.g. `from src.merge_policy import x` already caught by the package check
# above; this also catches a hypothetical `import merge_policy` if sys.path ever grew).
FORBIDDEN_MODULE_NAMES = {
    "merge_policy",
    "icp_scoring",
    "providers",
    "normalizer",
    "hubspot_client",
    "classifier_haiku",
    "validator_sonnet",
    "column_mapper",
    "file_loader",
}

# operator-claude-plugin's own flat modules (scripts/ is on sys.path per conftest.py) —
# never mistake these for undeclared third-party imports below.
# "report" was added in 26-02: report_enrichment.py reuses report.py's
# `_run_data`/`_node_output_items` traversal rather than re-implementing it.
LOCAL_MODULES = {"config_gate", "tabular", "dispatch", "preview", "extraction", "report"}

# PyPI package name differs from its import name for PyYAML only, among this plugin's
# three declared dependencies.
IMPORT_NAME_TO_PACKAGE = {"yaml": "pyyaml"}


def _plugin_source_files():
    """Every .py file under operator-claude-plugin/, excluding bytecode caches."""
    return [p for p in PLUGIN_ROOT.rglob("*.py") if "__pycache__" not in p.parts]


def _runtime_source_files():
    """Files the operator's own runtime actually executes — excludes tests/, which run
    under this repo's .venv and pytest, not the operator's plugin-local install."""
    return [
        p
        for p in _plugin_source_files()
        if "tests" not in p.relative_to(PLUGIN_ROOT).parts
    ]


def _imported_module_names(path: Path):
    """Every top-level module name a file imports, parsed with ast."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def test_scan_found_at_least_one_plugin_source_file():
    """Non-vacuity: this guard cannot pass by scanning nothing."""
    assert len(_plugin_source_files()) > 0


def test_no_plugin_file_imports_a_repo_backend_package_or_named_module():
    offenders = {}
    for path in _plugin_source_files():
        for name in _imported_module_names(path):
            top = name.split(".")[0]
            leaf = name.split(".")[-1]
            if top in FORBIDDEN_TOP_LEVEL_PACKAGES or leaf in FORBIDDEN_MODULE_NAMES:
                offenders.setdefault(str(path.relative_to(PLUGIN_ROOT)), []).append(name)
    assert not offenders, (
        f"plugin file(s) import repo backend module(s), violating PLUGIN-04: {offenders}"
    )


def test_every_third_party_import_is_declared_in_requirements_txt():
    """D-01's independent-replaceability property: an undeclared import is how a plugin
    quietly stops being replaceable without the repo root's own dependency set."""
    requirements_path = PLUGIN_ROOT / "requirements.txt"
    declared = set()
    for line in requirements_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = re.split(r"[><=]", line, maxsplit=1)[0].strip().lower()
        declared.add(pkg)

    stdlib = set(sys.stdlib_module_names)

    offenders = set()
    for path in _runtime_source_files():
        for name in _imported_module_names(path):
            top = name.split(".")[0]
            if top in stdlib or top in LOCAL_MODULES:
                continue
            package = IMPORT_NAME_TO_PACKAGE.get(top, top).lower()
            if package not in declared:
                offenders.add(top)

    assert not offenders, (
        f"import(s) not declared in operator-claude-plugin/requirements.txt: {offenders}"
    )
