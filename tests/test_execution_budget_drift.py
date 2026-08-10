# tests/test_execution_budget_drift.py
#
# Phase 45 Plan 03 (D-04): two committed artifacts each carry a copy of the same numbers —
# config/execution_budget.yaml (the backend's source of truth) and
# operator-claude-plugin/config/operator.local.example.json (the plugin's config mirror,
# because the unattended sweep must not gain a runtime filesystem dependency on a backend
# checkout that could move). Nothing else connects them. If the two drift, the burn-rate
# alarm (Phase 45-01) and the runtime cadence budget floor (Phase 45-02) silently watch a
# different ceiling than the one tests/test_execution_budget.py enforces at build time.
#
# Everything is re-derived from the committed artifacts directly — never imported from
# either side's computed constants — mirroring tests/test_execution_budget.py's own header
# comment: a test that imports the number one side baked cannot see the two sides
# disagreeing.
#
# This test also performs the backend-to-plugin import direction, which
# operator-claude-plugin/tests/test_no_backend_imports.py does NOT guard (that guard is
# plugin-to-backend only) and which scripts/june_run_arm.py already takes as precedent.
# n8n_cadence performs no I/O at import time — its transitive imports are copy, re, json,
# requests, n8n_control, n8n_read, all inert on import.
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SCRIPTS = ROOT / "operator-claude-plugin" / "scripts"
if str(PLUGIN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SCRIPTS))


def _load_budget():
    return yaml.safe_load((ROOT / "config" / "execution_budget.yaml").read_text())


def _load_plugin_example_config():
    path = ROOT / "operator-claude-plugin" / "config" / "operator.local.example.json"
    return json.loads(path.read_text())


def test_plugin_example_allowance_matches_the_budget_file():
    budget = _load_budget()
    plugin_config = _load_plugin_example_config()

    # Direct indexing on purpose — a missing key must fail, not default (T-44-07/T-45-13).
    budget_value = budget["monthly_execution_allowance"]
    plugin_value = plugin_config["n8n_monthly_execution_allowance"]

    for value, label in (
        (budget_value, "config/execution_budget.yaml's monthly_execution_allowance"),
        (plugin_value, "operator.local.example.json's n8n_monthly_execution_allowance"),
    ):
        assert isinstance(value, (int, float)) and not isinstance(value, bool), (
            f"{label} must be numeric, got {value!r} ({type(value).__name__}) — a quoted "
            "number would compare unequal in a confusing way rather than an obvious one")

    assert budget_value == plugin_value, (
        "config/execution_budget.yaml's monthly_execution_allowance "
        f"({budget_value!r}) and operator-claude-plugin/config/operator.local.example.json's "
        f"n8n_monthly_execution_allowance ({plugin_value!r}) have drifted apart. "
        "config/execution_budget.yaml is the source of truth; the plugin example mirrors "
        "it. Update the plugin example to match.")


def test_plugin_example_floor_share_matches_the_budget_file():
    budget = _load_budget()
    plugin_config = _load_plugin_example_config()

    # Direct indexing on purpose — a missing key must fail, not default (T-44-07/T-45-13).
    budget_value = budget["idle_floor_max_share"]
    plugin_value = plugin_config["n8n_schedule_floor_max_share"]

    for value, label in (
        (budget_value, "config/execution_budget.yaml's idle_floor_max_share"),
        (plugin_value, "operator.local.example.json's n8n_schedule_floor_max_share"),
    ):
        assert isinstance(value, (int, float)) and not isinstance(value, bool), (
            f"{label} must be numeric, got {value!r} ({type(value).__name__}) — a quoted "
            "number would compare unequal in a confusing way rather than an obvious one")

    assert budget_value == plugin_value, (
        "config/execution_budget.yaml's idle_floor_max_share "
        f"({budget_value!r}) and operator-claude-plugin/config/operator.local.example.json's "
        f"n8n_schedule_floor_max_share ({plugin_value!r}) have drifted apart. Why they must "
        "match: the runtime cadence budget floor (Phase 45-02) judges a schedule change "
        "against the plugin's share while tests/test_execution_budget.py judges the "
        "committed schedule against the YAML's — a divergence means the plugin permits a "
        "cadence the build then rejects, or refuses one the build allows.")


def test_cadence_ticks_per_month_agrees_with_the_budget_guard():
    import n8n_cadence
    from tests.test_execution_budget import TICKS_PER_MONTH as build_ticks

    runtime_ticks = n8n_cadence.TICKS_PER_MONTH

    # Non-vacuity: a rename on either side must not make this comparison pass by comparing
    # nothing (mirroring test_execution_budget.py's own triggers-non-empty guard).
    shared_keys = set(build_ticks) & set(runtime_ticks)
    assert shared_keys, (
        "n8n_cadence.TICKS_PER_MONTH and tests/test_execution_budget.py's TICKS_PER_MONTH "
        "share no keys at all — the comparison below would be vacuous; fix whichever side "
        "renamed its schedule-field keys")

    # Deliberately NOT an identity assertion on the key sets: n8n_cadence carries a
    # `seconds` row the build-time guard has no need of (no committed trigger uses
    # seconds), and requiring identical key sets would fail on a difference that is
    # correct. Only keys present on BOTH sides must agree in value.
    mismatches = {
        key: (build_ticks[key], runtime_ticks[key])
        for key in shared_keys
        if build_ticks[key] != runtime_ticks[key]
    }
    assert not mismatches, (
        "the 30-day month has been computed a third way — "
        "tests/test_execution_budget.py's TICKS_PER_MONTH and "
        "operator-claude-plugin's n8n_cadence.TICKS_PER_MONTH disagree on: "
        f"{mismatches}")
