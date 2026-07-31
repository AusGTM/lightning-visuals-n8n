"""operator-claude-plugin/scripts/n8n_cadence.py

Cadence in plain terms (28-04): read what a scheduled job does now, say it in a sentence,
take a free-form phrase, and either understand it or refuse honestly.

D-09 IS THE BINDING CONSTRAINT: schedule-expression syntax never reaches the operator, in
either direction. Not in a description, not in a refusal, not as a fallback for a phrase
the native fields cannot express. The module never round-trips through an expression
internally either, so there is no path by which one could leak into output.

D-09 also says the safety mechanism is the CONFIRMATION, not the parser's cleverness. This
module supplies the two halves confirmation needs — the parse, and the plain-language
description of what the parse means — and deliberately does not implement the loop itself.
28-05 owns operator wording. The caller shows the description, waits, and only then writes.

D-10: a phrase requiring the expression field is exactly the low-confidence interpretation
to refuse rather than emit as opaque syntax nobody sees explained. Every refusal carries a
reason and at least three worked examples; no refusal is a bare None.

`rule.interval` is an ARRAY — entries fire independently. "Every weekday at 9am and 5pm" is
two `weeks` entries, not one expression.
"""
import copy
import re

import n8n_control
import n8n_read

WEEKDAY_NAMES = {0: "Sunday", 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
                 5: "Friday", 6: "Saturday"}
WEEKDAYS_MON_FRI = [1, 2, 3, 4, 5]

# The native field types and their companion keys (28-RESEARCH.md Pattern 3). Note the
# deliberate absence of `cronExpression`: it is a real n8n field, and this module will not
# emit it. See D-10.
SUPPORTED_FIELDS = {
    "seconds": "secondsInterval",
    "minutes": "minutesInterval",
    "hours": "hoursInterval",
    "days": "daysInterval",
    "weeks": "weeksInterval",
    "months": "monthsInterval",
}

_EXAMPLES = [
    "every 15 minutes",
    "hourly",
    "every weekday at 9am and 5pm",
    "every day at 6am",
    "weekly",
    "monthly",
]


class CadenceRefused(Exception):
    """A phrase that could not be interpreted confidently. Carries examples, because a
    refusal without a way forward is just a dead end."""

    def __init__(self, reason, examples=None):
        self.reason = reason
        self.examples = list(examples) if examples else list(_EXAMPLES[:3])
        super().__init__(f"{reason} Try one of: {'; '.join(self.examples)}.")


def schedule_trigger_nodes(workflow):
    """Every Schedule Trigger node name in the workflow, discovered — never hardcoded."""
    names = []
    for node in (workflow or {}).get("nodes") or []:
        if isinstance(node, dict) and str(node.get("type", "")).endswith("scheduleTrigger"):
            names.append(node.get("name"))
    return [name for name in names if name]


def read_cadence(workflow, node_name):
    """The named node's interval array.

    A missing name raises with the workflow's ACTUAL Schedule Trigger names listed: a typo
    is the most likely operator-facing failure here, and a bare KeyError teaches nothing.
    """
    for node in (workflow or {}).get("nodes") or []:
        if isinstance(node, dict) and node.get("name") == node_name:
            interval = ((node.get("parameters") or {}).get("rule") or {}).get("interval")
            if not isinstance(interval, list):
                raise CadenceRefused(
                    f"{node_name!r} has no schedule interval to read.",
                    [f"try one of these scheduled jobs: {n}"
                     for n in schedule_trigger_nodes(workflow)[:3]] or _EXAMPLES[:3])
            return interval

    available = schedule_trigger_nodes(workflow)
    raise CadenceRefused(
        f"there is no scheduled job named {node_name!r} in this workflow. "
        f"The scheduled jobs here are: {', '.join(available) or 'none'}.",
        available[:3] or _EXAMPLES[:3])


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _clock(entry):
    """'at 9:00am' / 'at 5:30pm', or '' when the entry names no time of day."""
    hour = entry.get("triggerAtHour")
    minute = entry.get("triggerAtMinute")
    if hour is None and minute is None:
        return ""
    hour = 0 if hour is None else int(hour)
    minute = 0 if minute is None else int(minute)
    suffix = "am" if hour < 12 else "pm"
    display = hour % 12 or 12
    return f" at {display}:{minute:02d}{suffix}"


def _plural(count, noun):
    return f"{noun}" if count == 1 else f"{count} {noun}s"


def describe_cadence(interval):
    """Render an interval array as plain language. The ONLY thing an operator ever sees
    describing a schedule, so nothing it emits may contain expression syntax."""
    if not interval:
        return "no schedule is set"

    clauses = []
    for entry in interval:
        if not isinstance(entry, dict):
            continue
        field = entry.get("field")

        if field == "cronExpression":
            # Present in the schema, never emitted by this module — but a workflow edited
            # by hand in the n8n UI can carry one, and describing it as raw syntax would
            # break D-09 exactly where it matters most.
            clauses.append("on a custom schedule this plugin cannot describe in plain "
                           "language — check it in n8n directly")
            continue

        if field not in SUPPORTED_FIELDS:
            clauses.append("on an unrecognised schedule")
            continue

        every = entry.get(SUPPORTED_FIELDS[field], 1) or 1
        every = int(every)

        if field == "weeks":
            days = entry.get("triggerOnWeekdays")
            if days:
                names = [WEEKDAY_NAMES.get(int(d), str(d)) for d in days]
                if sorted(int(d) for d in days) == WEEKDAYS_MON_FRI:
                    when = "every weekday"
                elif len(names) == 1:
                    when = f"every {names[0]}"
                else:
                    when = f"every {', '.join(names[:-1])} and {names[-1]}"
            else:
                when = "once a week" if every == 1 else f"every {_plural(every, 'week')}"
            clauses.append(when + _clock(entry))
            continue

        if field == "months":
            day = entry.get("triggerAtDayOfMonth")
            base = "once a month" if every == 1 else f"every {_plural(every, 'month')}"
            if day is not None:
                base += f" on the {_ordinal(int(day))}"
            clauses.append(base + _clock(entry))
            continue

        if field == "days":
            base = "once a day" if every == 1 else f"every {_plural(every, 'day')}"
            clauses.append(base + _clock(entry))
            continue

        if field == "hours":
            base = "once an hour" if every == 1 else f"every {_plural(every, 'hour')}"
            minute = entry.get("triggerAtMinute")
            if minute is not None:
                base += f" at {int(minute)} minutes past"
            clauses.append(base)
            continue

        unit = "minute" if field == "minutes" else "second"
        clauses.append(f"every {_plural(every, unit)}")

    if not clauses:
        return "no schedule is set"
    if len(clauses) == 1:
        return clauses[0]
    return ", and ".join([", ".join(clauses[:-1]), clauses[-1]]) \
        if len(clauses) > 2 else " and ".join(clauses)


# Anything that looks like the operator pasted schedule syntax rather than describing
# intent. Refused rather than passed through — D-09 runs in both directions.
_EXPRESSION_SHAPED = re.compile(r"^[\d*/,\-\s]+$")


def parse_cadence(phrase):
    """A free-form phrase -> an interval array, using native field types ONLY.

    Raises `CadenceRefused` whenever the phrase is ambiguous, already expression syntax, or
    would need the expression field to express.
    """
    if phrase is None:
        raise CadenceRefused("no schedule phrase was given.")

    text = " ".join(str(phrase).strip().lower().split())
    if not text:
        raise CadenceRefused("no schedule phrase was given.")

    if _EXPRESSION_SHAPED.match(text) and any(ch in text for ch in "*/,-"):
        raise CadenceRefused(
            "that looks like schedule expression syntax rather than a description. "
            "Tell me the schedule in your own words instead and I will read it back to "
            "you before anything changes.")

    # Patterns the native fields genuinely cannot express — refused by name, per D-10,
    # rather than silently emitted as an expression.
    for marker in ("third ", "second ", "last ", "first "):
        if marker in text and any(day in text for day in
                                  ("monday", "tuesday", "wednesday", "thursday",
                                   "friday", "saturday", "sunday")):
            raise CadenceRefused(
                "a schedule like that needs a pattern I cannot express without falling "
                "back to raw schedule syntax, which I will not do because you would never "
                "see it explained.")

    # "every weekday at 9am and 5pm" -> two weeks entries.
    hours = _times_of_day(text)
    if "weekday" in text:
        if not hours:
            hours = [9]
        return [{"field": "weeks", "weeksInterval": 1,
                 "triggerOnWeekdays": list(WEEKDAYS_MON_FRI),
                 "triggerAtHour": hour, "triggerAtMinute": minute}
                for hour, minute in hours]

    named_day = _named_weekday(text)
    if named_day is not None:
        hour, minute = (hours or [(9, 0)])[0]
        return [{"field": "weeks", "weeksInterval": 1, "triggerOnWeekdays": [named_day],
                 "triggerAtHour": hour, "triggerAtMinute": minute}]

    if text in ("hourly", "every hour", "once an hour"):
        return [{"field": "hours", "hoursInterval": 1}]
    if text in ("daily", "every day", "once a day") and not hours:
        return [{"field": "days", "daysInterval": 1}]
    if text in ("weekly", "every week", "once a week"):
        return [{"field": "weeks", "weeksInterval": 1}]
    if text in ("monthly", "every month", "once a month"):
        return [{"field": "months", "monthsInterval": 1}]

    if ("day" in text or "daily" in text) and hours:
        return [{"field": "days", "daysInterval": 1,
                 "triggerAtHour": hour, "triggerAtMinute": minute}
                for hour, minute in hours]

    match = re.fullmatch(r"every (\d+) (second|minute|hour|day|week|month)s?", text)
    if match:
        every = int(match.group(1))
        if every < 1:
            raise CadenceRefused("a schedule has to repeat at least once.")
        field = match.group(2) + "s"
        return [{"field": field, SUPPORTED_FIELDS[field]: every}]

    raise CadenceRefused(
        f"I could not confidently work out what {str(phrase).strip()!r} means as a "
        f"schedule, and I would rather ask than guess — a misread schedule changes how "
        f"often the backend spends money.")


def _times_of_day(text):
    """[(hour, minute), ...] for every time named in the phrase, in order."""
    found = []
    for match in re.finditer(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text):
        hour = int(match.group(1)) % 12
        minute = int(match.group(2) or 0)
        if match.group(3) == "pm":
            hour += 12
        found.append((hour, minute))
    if not found:
        for match in re.finditer(r"at (\d{1,2}):(\d{2})", text):
            found.append((int(match.group(1)), int(match.group(2))))
    return found


def _named_weekday(text):
    for number, name in WEEKDAY_NAMES.items():
        if name.lower() in text:
            return number
    return None


# ---------------------------------------------------------------------------------------
# Task 2 — per-job enable/disable, the ONE field D-25 widened the allowlist by
# ---------------------------------------------------------------------------------------

def job_enabled(workflow, node_name):
    """Whether one scheduled job is currently on. n8n marks a node off with
    `disabled: true`; absent means enabled."""
    for node in (workflow or {}).get("nodes") or []:
        if isinstance(node, dict) and node.get("name") == node_name:
            return not bool(node.get("disabled"))
    raise CadenceRefused(
        f"there is no scheduled job named {node_name!r} in this workflow. "
        f"The scheduled jobs here are: "
        f"{', '.join(schedule_trigger_nodes(workflow)) or 'none'}.",
        schedule_trigger_nodes(workflow)[:3] or _EXAMPLES[:3])


def set_job_enabled(workflow, node_name, enabled):
    """Toggle ONE Schedule Trigger node's `disabled` boolean, in place.

    Why not workflow-level activate/deactivate: `LV Scheduled Maintenance (Cloud)` carries
    FIVE Schedule Triggers, so deactivating the workflow to switch off one job would stop
    all five — including the review poller and the stuck-lock sweep. D-25 (amendment #6)
    resolved this on 2026-07-31 by widening the mutation allowlist by exactly one field.
    That decision is MADE; this implements it and does not re-open it.
    """
    for node in (workflow or {}).get("nodes") or []:
        if not isinstance(node, dict) or node.get("name") != node_name:
            continue
        if not str(node.get("type", "")).endswith("scheduleTrigger"):
            raise CadenceRefused(
                f"{node_name!r} is not a scheduled job, so it cannot be switched on or "
                f"off this way. The allowlist covers Schedule Trigger nodes only.")
        if enabled:
            node.pop("disabled", None)
        else:
            node["disabled"] = True
        return workflow

    raise CadenceRefused(
        f"there is no scheduled job named {node_name!r} in this workflow. "
        f"The scheduled jobs here are: "
        f"{', '.join(schedule_trigger_nodes(workflow)) or 'none'}.",
        schedule_trigger_nodes(workflow)[:3] or _EXAMPLES[:3])


def _set_interval_in_place(workflow, node_name, interval):
    """Replace ONE Schedule Trigger node's interval, in place. Pure; the network wrapper
    `set_cadence` below runs the structural diff and the read-back."""
    if not isinstance(interval, list) or not interval:
        raise CadenceRefused("a schedule needs at least one interval entry.")
    for entry in interval:
        if not isinstance(entry, dict) or entry.get("field") not in SUPPORTED_FIELDS:
            raise CadenceRefused(
                "that interval uses a field this plugin does not write. Only the native "
                "schedule fields are permitted, never an expression.")

    for node in (workflow or {}).get("nodes") or []:
        if isinstance(node, dict) and node.get("name") == node_name:
            node.setdefault("parameters", {}).setdefault("rule", {})["interval"] = interval
            return workflow

    raise CadenceRefused(
        f"there is no scheduled job named {node_name!r} in this workflow.",
        schedule_trigger_nodes(workflow)[:3] or _EXAMPLES[:3])


# ---------------------------------------------------------------------------------------
# The two mutations. Both go through 28-01's ONE pipeline; neither may widen to cover the
# other's field, or the field-level guard stops meaning anything. An operator wanting both
# changes performs both, each with its own confirmation and its own read-back.
# ---------------------------------------------------------------------------------------

def _assert_only_field_changed(original_node, modified_node, field_path):
    """Reverting the one permitted field must reproduce the original node exactly.

    Node-level allowlisting alone would permit rewriting a trigger's whole `parameters`
    block under cover of a one-field change. Same narrowing 28-03 applies to gate nodes.
    """
    rebuilt = copy.deepcopy(modified_node)
    if field_path == ("disabled",):
        if "disabled" in original_node:
            rebuilt["disabled"] = original_node["disabled"]
        else:
            rebuilt.pop("disabled", None)
    else:
        prior = ((original_node.get("parameters") or {}).get("rule") or {}).get("interval")
        rebuilt.setdefault("parameters", {}).setdefault("rule", {})["interval"] = prior

    if rebuilt != original_node:
        raise CadenceRefused(
            f"refusing: node {original_node.get('name')!r} differs outside "
            f"{'.'.join(field_path)}. Only that one field may change in this mutation.")


def _node_by_name(workflow, node_name):
    for node in (workflow or {}).get("nodes") or []:
        if isinstance(node, dict) and node.get("name") == node_name:
            return node
    return None


def set_schedule_enabled(workflow_id, node_name, enabled, config, transport=None):
    """Switch ONE scheduled job on or off — D-25's allowlist widening, implemented.

    There is no refusal branch for the capability itself: per-job disable is something this
    phase ships. `LV Scheduled Maintenance (Cloud)` carries five Schedule Triggers, so
    workflow-level deactivate would stop all five.
    """
    import requests as _requests
    transport = transport if transport is not None else _requests

    prior = {}

    def _mutate(workflow):
        node = _node_by_name(workflow, node_name)
        if node is None:
            raise CadenceRefused(
                f"there is no scheduled job named {node_name!r} in this workflow. "
                f"The scheduled jobs here are: "
                f"{', '.join(schedule_trigger_nodes(workflow)) or 'none'}.",
                schedule_trigger_nodes(workflow)[:3] or _EXAMPLES[:3])
        original_node = copy.deepcopy(node)
        prior["enabled"] = not bool(node.get("disabled"))
        set_job_enabled(workflow, node_name, enabled)
        _assert_only_field_changed(original_node, _node_by_name(workflow, node_name),
                                   ("disabled",))

    def _verify(workflow):
        node = _node_by_name(workflow, node_name)
        return None if node is None else not bool(node.get("disabled"))

    result = n8n_control.apply_mutation(
        workflow_id, _mutate, [node_name], config, verify_fn=_verify, transport=transport,
        action=f"{'enable' if enabled else 'disable'} the scheduled job {node_name!r}")

    was = prior.get("enabled")
    if was is not None:
        result.reversal = (
            f"this job was {'running' if was else 'switched off'}; to undo, I'll switch it "
            f"back {'on' if was else 'off'}.")
    return result


def set_cadence(workflow_id, node_name, interval, config, transport=None):
    """Re-time ONE scheduled job, with the prior cadence quoted back in plain language."""
    import requests as _requests
    transport = transport if transport is not None else _requests

    if isinstance(interval, CadenceRefused):
        raise CadenceRefused(
            "that schedule was never understood, so there is nothing to write. "
            f"({interval.reason})", interval.examples)
    if not isinstance(interval, list) or not interval:
        raise CadenceRefused("a schedule needs at least one interval entry.")

    prior = {}

    def _mutate(workflow):
        node = _node_by_name(workflow, node_name)
        if node is None:
            raise CadenceRefused(
                f"there is no scheduled job named {node_name!r} in this workflow. "
                f"The scheduled jobs here are: "
                f"{', '.join(schedule_trigger_nodes(workflow)) or 'none'}.",
                schedule_trigger_nodes(workflow)[:3] or _EXAMPLES[:3])
        original_node = copy.deepcopy(node)
        prior["interval"] = ((node.get("parameters") or {}).get("rule") or {}).get("interval")
        _set_interval_in_place(workflow, node_name, interval)
        _assert_only_field_changed(original_node, _node_by_name(workflow, node_name),
                                   ("parameters", "rule", "interval"))

    def _verify(workflow):
        node = _node_by_name(workflow, node_name)
        if node is None:
            return None
        # Structural, never string equality: key ordering in the returned JSON must not
        # produce a false failure.
        return ((node.get("parameters") or {}).get("rule") or {}).get("interval")

    result = n8n_control.apply_mutation(
        workflow_id, _mutate, [node_name], config, verify_fn=_verify, transport=transport,
        action=f"re-time the scheduled job {node_name!r}")

    if prior.get("interval") is not None:
        result.reversal = (f"this job ran {describe_cadence(prior['interval'])}; "
                           f"to undo, I'll set it back to that.")
    return result
