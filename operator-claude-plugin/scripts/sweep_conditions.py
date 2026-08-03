"""operator-claude-plugin/scripts/sweep_conditions.py

Pure functions over already-fetched data (29-03). No I/O, no clock, no client — the
import-graph guard depends on this module staying that way.

This slice ships exactly one condition: the stuck execution. It CONSUMES Phase 27's
already-computed verdict — the tri-state `stuck` key summarize_execution() put on each
summary, judged against stuck_threshold_minutes(config) — rather than re-deriving it.
There is no is_stuck() anywhere in the tree (D-14), and a second stuck definition that
drifts from Phase 27's is the exact failure 29-RESEARCH.md's Don't-Hand-Roll table names.

All three states survive end to end: True fires, False does not, and None — in flight
with a start time we could not read — fires its own distinct outcome. Rounding None down
to "fine" is the specific bug Phase 27 D-07b(i) exists to prevent: a run whose age we
cannot read is not a run that just started.
"""

STUCK = "stuck_execution"
STUCK_AGE_UNREADABLE = "stuck_age_unreadable"


def check_stuck(summaries):
    """Fired-condition dicts for every summary whose stuck verdict is True or None."""
    fired = []
    for summary in summaries or []:
        if not isinstance(summary, dict):
            continue
        verdict = summary.get("stuck")
        if verdict is False:
            continue
        if verdict is True:
            fired.append({
                "condition": STUCK,
                "execution_id": summary.get("execution_id"),
                "workflow_name": summary.get("workflow_name"),
                "running_for_minutes": summary.get("running_for_minutes"),
                "threshold_minutes": summary.get("stuck_threshold_minutes"),
                "reason": (
                    f"a run of {summary.get('workflow_name') or 'an unnamed workflow'} "
                    f"has been going for about "
                    f"{round(summary.get('running_for_minutes') or 0)} minutes — past "
                    f"the {summary.get('stuck_threshold_minutes')}-minute point where a "
                    f"run counts as wedged"),
            })
        elif verdict is None and summary.get("in_flight"):
            fired.append({
                "condition": STUCK_AGE_UNREADABLE,
                "execution_id": summary.get("execution_id"),
                "workflow_name": summary.get("workflow_name"),
                "running_for_minutes": None,
                "threshold_minutes": summary.get("stuck_threshold_minutes"),
                "reason": (
                    f"a run of {summary.get('workflow_name') or 'an unnamed workflow'} "
                    f"is in flight but its age could not be read, so whether it is "
                    f"wedged is unknown — unknown is not fine"),
            })
    return fired


def evaluate(gathered):
    """Every condition this slice knows, over one gather. 29-05 expands this list."""
    executions = (gathered or {}).get("executions") or {}
    if not executions.get("available"):
        return []          # nothing readable here; sweep_entry owes the D-15 notice
    return check_stuck(executions.get("summaries"))
