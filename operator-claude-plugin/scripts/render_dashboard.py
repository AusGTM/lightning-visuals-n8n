"""operator-claude-plugin/scripts/render_dashboard.py

The dashboard half of STATUS-05: the SAME status mapping `render_text.render_report()`
consumes, laid out as a page the operator can bookmark (D-09). Text stays the default;
this is what they get when they ask for the dashboard.

Two rules hold the surface together:

- **Same data, or it is a second source of truth.** Every sentence-level string here comes
  from `render_text`'s own helpers and every value from `status.render()`, so the two
  renderings cannot drift into disagreeing about what the backend is doing.
  `test_dashboard_parity.py` compares them against each other, not each against its own
  expectations.
- **The stamp is when the data was FETCHED, not when the page was drawn.** It is read out
  of the mapping. A dashboard republished from a cached mapping that stamped itself
  `now()` would be a stale reading wearing a fresh timestamp (T-27-23).

`dashboard_payload()` and `render_dashboard()` are pure: no network, no file, no store.
The stored artifact identifier is the skill's to load and save — a renderer that reached
for it could publish one run's data under another run's pointer.

Every value reaching the markup is escaped. Workflow names and raw error text arrive from
n8n; neither is trusted markup.
"""
import html as html_module

import render_text
import status

UNKNOWN = status.UNKNOWN

TITLE = "What the backend is doing"
READ_ONLY_NOTE = ("This is a read-only view. Nothing here was switched on or off, "
                  "started, stopped, or written to any record.")
UNKNOWN_NOTE = ("Anything reading “unknown” means the backend could not tell us — "
                "not that the answer is zero.")


def _live_writes(write_safety) -> list:
    """One row per write-safety flag, worded exactly as the text answer words it so the
    two cannot disagree about whether live writes are on."""
    rows = []
    for flag, read in (write_safety or {}).items():
        read = read if isinstance(read, dict) else {}
        if read.get("disagreement"):
            rows.append(f"{flag} {UNKNOWN} — the declaring nodes disagree")
        else:
            rows.append(f"{flag} {render_text._armed(read.get('value'))}")
    return rows or [f"Live writes to HubSpot: {UNKNOWN}"]


def _failures(failure):
    """(rows, note). A recognised cause is its sentence and who can act and nothing else
    — no code, no node, no stack (D-04c). An unrecognised one keeps its raw text as its
    own field so the layout can hold the two apart (D-05)."""
    if not isinstance(failure, dict) or not failure:
        return [], ""
    if not failure.get("available"):
        return [], f"Why it failed: {UNKNOWN} — {status.render(failure.get('reason'))}"

    findings = failure.get("findings") or []
    if not findings:
        return [], "Why it failed: nothing readable in that run's own output."

    rows = []
    for finding in findings:
        finding = finding if isinstance(finding, dict) else {}
        interpretation = bool(finding.get("is_interpretation"))
        count = finding.get("count")
        rows.append({
            "sentence": status.render(finding.get("sentence")),
            "who_can_act": status.render(finding.get("who_can_fix")),
            "raw": status.render(finding.get("raw")) if interpretation else None,
            "is_interpretation": interpretation,
            "count": count if isinstance(count, int) and count > 1 else 1,
        })
    return rows, ""


def _workflow_panel(entry) -> dict:
    last_run = entry.get("last_run") if isinstance(entry.get("last_run"), dict) else {}
    failures, note = _failures(entry.get("failure"))
    return {
        "name": status.render(entry.get("name")),
        "active": status.render(entry.get("active")),
        "live_writes": _live_writes(entry.get("write_safety")),
        "right_now": render_text._right_now(last_run),
        "last_run": render_text._last_run(last_run),
        "failures": failures,
        "failure_note": note,
    }


def dashboard_payload(report) -> dict:
    """The dashboard's data, from the same mapping the text answer is built from."""
    report = report if isinstance(report, dict) else {}
    collection = report.get("workflows") if isinstance(report.get("workflows"), dict) else {}
    backend = report.get("backend") if isinstance(report.get("backend"), dict) else {}
    counts = backend.get("counts") if isinstance(backend.get("counts"), dict) else {}

    notices = []
    if not collection.get("readable"):
        notices.append(f"The list of workflows is {UNKNOWN} — n8n did not answer that "
                       "read, so nothing below covers the workflows themselves.")
    elif not collection.get("workflows"):
        notices.append("n8n answered, and there are no workflows at all on this instance.")
    if not backend.get("available"):
        notices.append(f"The counts and provider balances are {UNKNOWN} — the backend "
                       f"status check did not answer ({status.render(backend.get('reason'))}).")

    balances = backend.get("balances") or []
    return {
        "title": TITLE,
        # From the mapping, never from now(): this says when the data was gathered.
        "fetched_at": status.render(backend.get("checked_at")),
        "notices": notices,
        "workflows": [_workflow_panel(entry)
                      for entry in (collection.get("workflows") or [])
                      if isinstance(entry, dict)],
        "counts": [{"label": label, "value": status.render(counts.get(key))}
                   for key, label in render_text.COUNT_LABELS],
        "providers": [{"provider": status.render((balance or {}).get("provider")),
                       "credits": status.render((balance or {}).get("credits"))}
                      for balance in balances if isinstance(balance, dict)],
        "credential_health": [status.render(entry)
                              for entry in (backend.get("credential_health") or [])],
        "read_only_note": READ_ONLY_NOTE,
    }


# --- markup ------------------------------------------------------------------------------

_STYLE = """
:root { color-scheme: light dark; }
body { font: 15px/1.5 system-ui, sans-serif; margin: 0; padding: 1.5rem;
       background: Canvas; color: CanvasText; }
h1 { font-size: 1.4rem; margin: 0 0 .25rem; }
.stamp { opacity: .75; font-size: .85rem; margin: 0 0 1.25rem; }
.notice { border-left: 3px solid currentColor; opacity: .85; padding: .4rem .75rem;
          margin: .5rem 0; }
section { border: 1px solid rgba(128,128,128,.35); border-radius: 8px;
          padding: .75rem 1rem; margin: 0 0 1rem; }
h2 { font-size: 1.05rem; margin: 0 0 .5rem; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: .3rem .5rem; border-bottom: 1px solid
         rgba(128,128,128,.2); vertical-align: top; }
th { font-weight: 600; width: 60%; }
.state { font-variant: small-caps; letter-spacing: .02em; }
.unknown { opacity: .7; font-style: italic; }
.failure { margin: .4rem 0 0; }
.raw { font-family: ui-monospace, monospace; font-size: .85rem; opacity: .8; }
footer { opacity: .75; font-size: .85rem; margin-top: 1.5rem; }
"""


def _e(value) -> str:
    """Escape, and mark an unknown so the eye can tell it from a real reading."""
    text = html_module.escape(str(value))
    return f'<span class="unknown">{text}</span>' if text == UNKNOWN else text


def _row(label, value) -> str:
    return f"<tr><th>{_e(label)}</th><td>{_e(value)}</td></tr>"


def _workflow_section(panel) -> str:
    parts = [f"<section><h2>{_e(panel['name'])}</h2>",
             "<table>",
             _row("Switched", panel["active"])]
    for line in panel["live_writes"]:
        parts.append(f"<tr><th>Live writes</th><td>{_e(line)}</td></tr>")
    parts.append(f"<tr><th>Right now</th><td>{_e(panel['right_now'])}</td></tr>")
    parts.append(f"<tr><th>Last run</th><td>{_e(panel['last_run'])}</td></tr>")
    parts.append("</table>")

    if panel["failure_note"]:
        parts.append(f'<p class="failure">{_e(panel["failure_note"])}</p>')
    for failure in panel["failures"]:
        seen = (f" (seen {failure['count']} times)" if failure["count"] > 1 else "")
        if failure["is_interpretation"]:
            parts.append(
                '<p class="failure">Not a failure signature this plugin recognises'
                f'{_e(seen)}. The next line is an interpretation, not a known cause:'
                f'<br>interpretation: {_e(failure["sentence"])}'
                f'<br><span class="raw">raw error text: {_e(failure["raw"])}</span>'
                f'<br>who can act: {_e(failure["who_can_act"])}</p>')
        else:
            parts.append(f'<p class="failure">{_e(failure["sentence"])}{_e(seen)}'
                         f'<br>who can act: {_e(failure["who_can_act"])}</p>')
    parts.append("</section>")
    return "".join(parts)


def render_dashboard(report) -> str:
    """The whole dashboard as one self-contained HTML document, ready to publish."""
    payload = dashboard_payload(report)

    body = [f"<h1>{_e(payload['title'])}</h1>",
            f'<p class="stamp">Data fetched at {_e(payload["fetched_at"])}. '
            f'{_e(UNKNOWN_NOTE)}</p>']
    body.extend(f'<p class="notice">{_e(notice)}</p>' for notice in payload["notices"])
    body.extend(_workflow_section(panel) for panel in payload["workflows"])

    body.append("<section><h2>Records waiting on a human</h2><table>")
    body.extend(_row(row["label"], row["value"]) for row in payload["counts"])
    body.append("</table></section>")

    body.append("<section><h2>Data providers</h2><table>")
    if payload["providers"]:
        body.extend(_row(f"{row['provider']} credits remaining", row["credits"])
                    for row in payload["providers"])
    else:
        body.append(_row("Balances", UNKNOWN))
    if payload["credential_health"]:
        body.extend(_row("Credential health", line)
                    for line in payload["credential_health"])
    else:
        body.append(_row("Credential health", UNKNOWN))
    body.append("</table></section>")

    body.append(f"<footer>{_e(payload['read_only_note'])}</footer>")

    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>{_e(payload['title'])}</title><style>{_STYLE}</style></head>"
            f"<body>{''.join(body)}</body></html>")


if __name__ == "__main__":
    import json

    import config_gate

    try:
        _cfg = config_gate.load_config()
        _report = render_text.attach_failures(_cfg, status.full_report(_cfg))
    except config_gate.ConfigError as _e_:
        print(json.dumps({"ok": False, "error": str(_e_)}))
        raise SystemExit(1)

    print(render_dashboard(_report))
