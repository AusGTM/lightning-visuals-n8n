"""operator-claude-plugin/scripts/render_text.py

Turns the assembled status mapping into the plain-language answer an operator reads
(D-09: conversational text is this surface's default form; the dashboard is a thing you
ask for, and plan 27-05 wires it).

Every backend-supplied datum is already routed through `status.render()` at composition
time, and everything this module adds goes through it too — so a null cannot become a
blank on this path. "unknown" and "0" are opposite findings and a blank reads as healthy
(D-08, STATUS-06).

Two rules the shape of the output exists to serve:

- A stuck run states its own age and the threshold in the same sentence. The threshold is
  a carried convention rather than a measured value (27-RESEARCH.md A2), so the operator
  has to be able to judge the call rather than take the verdict on faith.
- A recognised failure gets its plain sentence and who can act, and nothing else — no
  status code, no node name, no stack (D-04c). An UNRECOGNISED one keeps its
  interpretation label and its raw text visibly separated from the interpretation, so the
  operator can see which part the surface is confident about (D-05).

Reads only. Nothing in this module turns anything on or off or writes to any record.
"""
import requests

import execution_errors
import n8n_read
import status

UNKNOWN = status.UNKNOWN

# The operator-facing name for each count the backend returns. Wording, not logic — the
# values arrive already rendered.
COUNT_LABELS = (
    ("companies_requested_unresolved", "Companies queued for enrichment"),
    ("contacts_requested_unresolved", "Contacts queued for enrichment"),
    ("companies_awaiting_review", "Companies waiting on a review decision"),
    ("contacts_awaiting_review", "Contacts waiting on a review decision"),
)


def _minutes(value):
    return UNKNOWN if value is None else f"{round(float(value))}"


def _right_now(last_run) -> str:
    """In flight, wedged, or idle — and the evidence for whichever it is."""
    threshold = _minutes(last_run.get("stuck_threshold_minutes"))
    running_for = last_run.get("running_for_minutes")

    if last_run.get("in_flight") is None:
        return f"Right now: {UNKNOWN} — the run state could not be read."
    if not last_run.get("in_flight"):
        return "Right now: nothing running."
    if last_run.get("stuck") is True:
        return (f"Right now: running, and it has been going for {_minutes(running_for)} "
                f"minutes — past the {threshold} minutes this plugin treats as wedged. "
                "That threshold is a convention, not a measured figure, so judge it "
                "against how long this job normally takes.")
    if running_for is None:
        return (f"Right now: running, but for how long is {UNKNOWN} — its start time "
                "could not be read, so it cannot be judged against the "
                f"{threshold}-minute wedged mark.")
    return (f"Right now: running, {_minutes(running_for)} minutes so far "
            f"(wedged mark is {threshold} minutes).")


def _last_run(last_run) -> str:
    if last_run.get("error"):
        return f"Last run: {UNKNOWN} — that read did not come back."
    if last_run.get("never_run"):
        return "Last run: never — this workflow has no execution history at all."
    return f"Last run: {status.render(last_run.get('status'))}."


def _armed(value) -> str:
    """The baked flag literal is the STRING "true"/"false", so it never reaches
    `render()`'s boolean branch. Map it explicitly — and only it, so an absent or
    unrecognised literal still falls through to unknown rather than to a reassuring
    "off"."""
    return {"true": "on", "false": "off"}.get(value, status.render(value))


def _write_safety(write_safety) -> str:
    parts = []
    for flag, read in (write_safety or {}).items():
        read = read if isinstance(read, dict) else {}
        if read.get("disagreement"):
            parts.append(f"{flag} {UNKNOWN} — the declaring nodes disagree")
        else:
            parts.append(f"{flag} {_armed(read.get('value'))}")
    return "Live writes to HubSpot: " + ("; ".join(parts) if parts else UNKNOWN) + "."


def render_failure(finding) -> list:
    """One harvested failure, as the operator should read it.

    A recognised cause is the sentence and the attribution, full stop. An unrecognised one
    is labelled as an interpretation with its raw text on its own line — the guardrail is
    only worth what its presentation makes visible.
    """
    finding = finding if isinstance(finding, dict) else {}
    seen = finding.get("count") or 1
    times = f" (seen {seen} times)" if isinstance(seen, int) and seen > 1 else ""

    if finding.get("is_interpretation"):
        return [
            f"  - Not a failure signature this plugin recognises{times}. "
            "Everything on the next line is an interpretation, not a known cause:",
            f"    interpretation: {status.render(finding.get('sentence'))}",
            f"    raw error text: {status.render(finding.get('raw'))}",
            f"    who can act: {status.render(finding.get('who_can_fix'))}",
        ]
    return [
        f"  - {status.render(finding.get('sentence'))}{times}",
        f"    who can act: {status.render(finding.get('who_can_fix'))}",
    ]


def _failure_block(failure) -> list:
    if not isinstance(failure, dict):
        return []
    if not failure.get("available"):
        return [f"Why it failed: {UNKNOWN} — {status.render(failure.get('reason'))}"]
    findings = failure.get("findings") or []
    if not findings:
        return ["Why it failed: nothing readable in that run's own output."]
    lines = ["Why it failed:"]
    for finding in findings:
        lines.extend(render_failure(finding))
    return lines


def render_workflow(entry) -> str:
    entry = entry if isinstance(entry, dict) else {}
    last_run = entry.get("last_run") if isinstance(entry.get("last_run"), dict) else {}
    lines = [
        f"## {status.render(entry.get('name'))}",
        f"Switched {status.render(entry.get('active'))}.",
        _write_safety(entry.get("write_safety")),
        _right_now(last_run),
        _last_run(last_run),
    ]
    lines.extend(_failure_block(entry.get("failure")))
    return "\n".join(lines)


def render_records_needing_a_human(backend) -> str:
    backend = backend if isinstance(backend, dict) else {}
    counts = backend.get("counts") if isinstance(backend.get("counts"), dict) else {}
    lines = ["## Records waiting on a human"]
    if not backend.get("available"):
        lines.append(f"These counts are {UNKNOWN} right now — the backend status check "
                     f"did not answer ({status.render(backend.get('reason'))}).")
    for key, label in COUNT_LABELS:
        lines.append(f"- {label}: {status.render(counts.get(key))}")
    return "\n".join(lines)


def render_sources(backend) -> str:
    backend = backend if isinstance(backend, dict) else {}
    lines = ["## Data providers"]
    balances = backend.get("balances") or []
    if balances:
        for balance in balances:
            balance = balance if isinstance(balance, dict) else {}
            lines.append(f"- {status.render(balance.get('provider'))}: "
                         f"{status.render(balance.get('credits'))} credits remaining")
    else:
        lines.append(f"- Balances: {UNKNOWN}")

    health = backend.get("credential_health") or []
    lines.append("Credential health: " +
                 ("; ".join(status.render(entry) for entry in health) if health else UNKNOWN))
    lines.append(f"Checked at: {status.render(backend.get('checked_at'))}.")
    return "\n".join(lines)


def render_report(report) -> str:
    """The whole answer, in one piece of text."""
    report = report if isinstance(report, dict) else {}
    collection = report.get("workflows") if isinstance(report.get("workflows"), dict) else {}
    backend = report.get("backend") if isinstance(report.get("backend"), dict) else {}

    blocks = ["# What the backend is doing"]
    if not collection.get("readable"):
        blocks.append(f"The list of workflows is {UNKNOWN} — n8n did not answer that "
                      "read, so nothing below covers the workflows themselves.")
    elif not collection.get("workflows"):
        blocks.append("n8n answered, and there are no workflows at all on this instance.")
    else:
        blocks.extend(render_workflow(entry) for entry in collection["workflows"])

    blocks.append(render_records_needing_a_human(backend))
    blocks.append(render_sources(backend))
    blocks.append("This is a read-only check. Nothing here was switched on or off, "
                  "started, stopped, or written to any record.")
    return "\n\n".join(blocks)


def attach_failures(config: dict, report: dict, transport=requests.get) -> dict:
    """Fetch the one large detail payload ONLY for a run already known to have failed.

    T-27-18: the gate is here, at the call site, not inside `n8n_read.get_execution`. A
    healthy or in-flight run is never pulled in full.
    """
    collection = report.get("workflows") if isinstance(report.get("workflows"), dict) else {}
    for entry in collection.get("workflows") or []:
        last_run = entry.get("last_run") if isinstance(entry.get("last_run"), dict) else {}
        if last_run.get("status") not in ("error", "crashed"):
            continue
        execution_id = last_run.get("execution_id")
        if not execution_id:
            continue
        body = n8n_read.get_execution(config, execution_id, transport=transport)
        entry["failure"] = (
            execution_errors.harvest_errors(body) if body is not None else
            {"available": False, "reason": "that execution's detail could not be read",
             "findings": []})
    return report


if __name__ == "__main__":
    import json

    import config_gate

    try:
        _cfg = config_gate.load_config()
        _report = status.full_report(_cfg)
    except config_gate.ConfigError as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    print(render_report(attach_failures(_cfg, _report)))
