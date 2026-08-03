"""operator-claude-plugin/scripts/sweep_notify.py

Fired conditions -> notice dicts (29-03). Pure; no I/O.

Attribution comes from error_table.translate() — imported, never mirrored — so its
unmatched-cause-defaults-to-admin guardrail applies by construction (D-09, D-18). A
cause the table does not recognise is an admin's problem until a human says otherwise.

Format is bound to the surface 29-01 observed (29-HOST-PROBE.md §A5): the banner budget
is ONE line, so every notice carries a one-line `headline` for the osascript banner and
a multi-line `detail` for the log. A notice never instructs the operator to run a
command or open a terminal — it points at the plugin's own control surface instead
(REQUIREMENTS.md's operator boundary).
"""
import error_table

# Where a fixable-by-operator notice points. Phase 28's surface, by skill name — never
# a shell command.
CONTROL_SURFACE = "the backend-control skill in this plugin"


def _attribution(reason):
    """error_table's verdict for this cause. Unmatched -> admin, guardrail included."""
    verdict = error_table.translate(reason)
    return verdict.get("who_can_fix") or "admin"


def render(fired):
    """Notice dicts for a list of fired conditions. Empty in, empty out — this module
    never invents an all-clear (NOTICE-04's silence is composed upstream by having
    nothing to render)."""
    notices = []
    for condition in fired or []:
        who = _attribution(condition.get("reason"))
        workflow = condition.get("workflow_name") or "a backend workflow"
        headline = f"LV backend: {workflow} needs a look — {condition.get('condition')}"
        detail_lines = [
            condition.get("reason") or "a condition fired without a reason recorded",
            (f"Who can act: {'you, from ' + CONTROL_SURFACE if who == 'operator' else 'your n8n admin'}."),
            "This sweep only reads — nothing was changed, stopped, or retried.",
        ]
        notices.append({
            "condition": condition.get("condition"),
            "headline": headline,
            "detail": "\n".join(detail_lines),
            "who_can_fix": who,
            "execution_id": condition.get("execution_id"),
        })
    return notices
