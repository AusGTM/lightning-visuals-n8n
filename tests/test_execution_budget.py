# tests/test_execution_budget.py
#
# Phase 44 Plan 02 (CAP-03): the shipped schedule's monthly execution FLOOR — the cost of
# every schedule trigger firing and finding nothing — must fit inside the configured share
# of the plan allowance.
#
# The case this guard is designed to catch: the v0.7 schedule ran three sub-daily triggers
# whose idle floor alone was roughly 2.6x the ENTIRE 2,500/month allowance while doing no
# work — and nothing in the repo said so. A future re-timing that blows the budget must
# fail HERE, naming the offending trigger, before it ships.
#
# Everything is re-derived from the committed artifacts (n8n/wf_*_cloud.json) plus
# config/execution_budget.yaml — never imported from the builder's computed constants,
# mirroring tests/test_field_policy_conformance.py: a test that imports the number the
# builder baked cannot see the builder and the config disagreeing.
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# The same arithmetic scripts/build_cloud_workflows.py's _schedule_trigger documents
# (30-day month): 15 minutes = 2,880/month per trigger, hourly = 720, daily = 30.
TICKS_PER_MONTH = {
    "minutes": 43200.0,
    "hours": 720.0,
    "days": 30.0,
    "weeks": 30.0 / 7.0,
    "months": 1.0,
}


def _shipped_schedule_triggers():
    """Every scheduleTrigger interval entry in every committed cloud artifact, as
    (workflow_file, node_name, field, interval_value) tuples."""
    found = []
    for wf_path in sorted(ROOT.glob("n8n/wf_*_cloud.json")):
        wf = json.loads(wf_path.read_text())
        for node in wf.get("nodes", []):
            if node.get("type") != "n8n-nodes-base.scheduleTrigger":
                continue
            for entry in node["parameters"]["rule"]["interval"]:
                field = entry["field"]
                interval = entry.get(f"{field}Interval", 1)
                found.append((wf_path.name, node["name"], field, interval))
    return found


def test_shipped_schedule_idle_floor_fits_the_configured_budget_share():
    budget = yaml.safe_load((ROOT / "config" / "execution_budget.yaml").read_text())
    # Direct indexing on purpose — a missing config key must fail, not default (T-44-07).
    allowance = budget["monthly_execution_allowance"]
    max_share = budget["idle_floor_max_share"]

    triggers = _shipped_schedule_triggers()
    # Non-vacuity: an artifact-shape change (node type rename, glob miss) could otherwise
    # make this pass by measuring nothing.
    assert triggers, (
        "no n8n-nodes-base.scheduleTrigger found in any committed n8n/wf_*_cloud.json — "
        "the budget guard would be vacuous; fix the artifact glob or the node-type match")

    costs = []
    for wf_name, node_name, field, interval in triggers:
        assert field in TICKS_PER_MONTH, (
            f"{wf_name}:{node_name} uses schedule field {field!r} with no documented "
            "ticks-per-month arithmetic — extend TICKS_PER_MONTH here AND "
            "_schedule_trigger's docstring, deliberately")
        assert interval >= 1, f"{wf_name}:{node_name} has a nonsensical interval {interval!r}"
        costs.append((wf_name, node_name, field, interval, TICKS_PER_MONTH[field] / interval))

    floor = sum(cost for *_ignored, cost in costs)
    ceiling = allowance * max_share
    detail = "\n".join(
        f"  {wf_name}: {node_name!r} (every {interval} {field}) -> {cost:.1f} executions/month"
        for wf_name, node_name, field, interval, cost in costs)
    assert floor <= ceiling, (
        f"the shipped schedule's idle floor is {floor:.1f} executions/month, over the "
        f"configured budget share ({max_share} x {allowance} = {ceiling:.0f}). "
        f"Contributing triggers:\n{detail}\n"
        "Re-time the offending trigger(s) or deliberately raise idle_floor_max_share in "
        "config/execution_budget.yaml.")
