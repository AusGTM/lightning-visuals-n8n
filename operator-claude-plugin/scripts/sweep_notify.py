"""operator-claude-plugin/scripts/sweep_notify.py

Fired conditions -> notice dicts (29-03; grouping and full attribution added 29-05
Task 3). Pure; no I/O.

Attribution comes from error_table.translate() — imported, never mirrored — so its
unmatched-cause-defaults-to-admin guardrail applies by construction (D-09, D-18). A
cause the table does not recognise is an admin's problem until a human says otherwise,
and every notice now carries the FULL verdict (`who_can_fix`, `is_interpretation`, `raw`)
rather than just the attribution — so an unrecognised cause is visibly labelled as an
interpretation with its raw text shown, not silently passed off as a known fact.

Format is bound to the surface 29-01 observed (29-HOST-PROBE.md §A5): the banner budget
is ONE line, so every notice carries a one-line `headline` for the osascript banner and
a multi-line `detail` for the log (recorded as untruncated there). A notice never
instructs the operator to run a command or open a terminal — it points at the plugin's
own control surface instead (REQUIREMENTS.md's operator boundary).

ONE fired condition renders exactly as 29-03 shipped it. MORE THAN ONE groups into a
SINGLE delivery: several banners in a row is exactly the noise 29-CONTEXT.md warns turns
a sweep into one the operator learns to ignore. Ordered most-actionable-first (operator-
fixable before admin-only — the operator is the one reading the banner) and capped at
GROUPED_DETAIL_CEILING with a stated count of anything past that, never a silent drop.
29-HOST-PROBE.md's A5 recorded the log as untruncated but recorded no number for how many
grouped items stay legible in one delivery, so the cap is a conservative default pending
observation (Claude's Discretion per 29-CONTEXT.md), not a limit backed by a measurement.
"""
import error_table

# Where a fixable-by-operator notice points. Phase 28's surface, by skill name — never
# a shell command.
CONTROL_SURFACE = "the backend-control skill in this plugin"

# Conservative pending observation (see module docstring) — the log has room, but a
# delivery that lists everything unbounded is not obviously more useful than one that
# says "here are the top 5, and 12 more."
GROUPED_DETAIL_CEILING = 5


def _who_line(who):
    return f"Who can act: {'you, from ' + CONTROL_SURFACE if who == 'operator' else 'your n8n admin'}."


def _render_one(condition):
    """One fired condition -> one notice dict. Carries the FULL error_table verdict, not
    just who_can_fix — an unrecognised cause is visibly an interpretation with its raw
    text attached, never quietly treated as a known fact (D-05, D-18)."""
    reason = condition.get("reason")
    verdict = error_table.translate(reason)
    who = verdict.get("who_can_fix") or "admin"
    workflow = condition.get("workflow_name") or "a backend workflow"
    headline = f"LV backend: {workflow} needs a look — {condition.get('condition')}"

    detail_lines = [
        reason or "a condition fired without a reason recorded",
        _who_line(who),
        "This sweep only reads — nothing was changed, stopped, or retried.",
    ]
    if verdict.get("is_interpretation"):
        detail_lines.append(
            "This sweep does not recognise this failure signature; the above is an "
            f"interpretation rather than a known fact. Raw text: {verdict.get('raw')}")

    return {
        "condition": condition.get("condition"),
        "headline": headline,
        "detail": "\n".join(detail_lines),
        "who_can_fix": who,
        "is_interpretation": bool(verdict.get("is_interpretation")),
        "raw": verdict.get("raw"),
        "execution_id": condition.get("execution_id"),
    }


def _group(rendered_notices):
    """Several rendered notices -> ONE delivery: most-actionable-first, capped, with a
    stated count of anything past the cap rather than a silent drop."""
    ordered = sorted(rendered_notices,
                     key=lambda n: 0 if n["who_can_fix"] == "operator" else 1)
    shown, remaining = ordered[:GROUPED_DETAIL_CEILING], ordered[GROUPED_DETAIL_CEILING:]

    headline = (f"LV backend: {len(ordered)} things need a look — "
               f"start with {shown[0]['condition']}")
    detail_blocks = [f"[{notice['condition']}] {notice['detail']}" for notice in shown]
    if remaining:
        detail_blocks.append(
            f"...and {len(remaining)} more condition(s) not shown here — see the full "
            f"sweep log.")

    who = "operator" if any(n["who_can_fix"] == "operator" for n in ordered) else "admin"

    return [{
        "condition": "grouped",
        "headline": headline,
        "detail": "\n\n".join(detail_blocks),
        "who_can_fix": who,
        "is_interpretation": any(n["is_interpretation"] for n in ordered),
        "raw": None,
        "execution_id": None,
    }]


def render(fired):
    """Notice dicts for a list of fired conditions. Empty in, empty out — this module
    never invents an all-clear (NOTICE-04's silence is composed upstream by having
    nothing to render). One fired condition renders exactly as before; more than one
    groups into a single delivery rather than one banner per condition."""
    rendered = [_render_one(condition) for condition in fired or []]
    if len(rendered) <= 1:
        return rendered
    return _group(rendered)
