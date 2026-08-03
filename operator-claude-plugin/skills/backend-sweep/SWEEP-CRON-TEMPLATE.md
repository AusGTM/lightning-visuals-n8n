# Sweep Trigger Template — cron / launchd

**Audience: an admin, installing this on the operator's machine. Not the operator.** The
operator never opens a terminal, edits a config file, or runs a command — that rule holds
everywhere else in this plugin and holds here too. Nothing in this file is ever handed to
the operator to run themselves.

## What this installs, and why it is a second step

Installing this plugin does **not** install this trigger. The plugin ships the sweep's
*logic* (`scripts/sweep_entry.py`, the `backend-sweep` skill) and the trigger that fires it
unattended: a shipped `sh` wrapper, `skills/backend-sweep/lv-sweep-run.sh`, that runs
`sweep_entry.py` directly — no LLM, no Anthropic credential, nothing in the path that can
expire. That wrapper still needs a schedule pointed at it, and a schedule lives outside the
plugin's own packaging (it is not a git-tracked file the plugin ships), so it has to be
installed on purpose, by an admin, as an explicit second step.

This reproduces the trigger proven live under real cron on 2026-08-03 with no session
open, replacing an earlier design that shelled a headless LLM invocation on a schedule and
failed there **silently** — see `29-HOST-PROBE.md`'s dated amendment for why that earlier
design's own host probe missed the failure, and `29-06-FINDINGS.md` for the verbatim errors
(an expired credential with no refresh, `node` absent from cron's PATH). The delivery
mechanics §A5 recorded still hold: a one-line macOS Notification Center banner via
`osascript`, with full detail redirected to a log file, because the banner budget is one
short line and the log is where the rest survives.

## Step 1 — create the interpreter the wrapper runs

The wrapper needs a python with this plugin's own dependencies installed. The system
`python3` on macOS does not have `requests`, so a schedule pointed at it fails on import —
measured, not assumed. Create a dedicated virtualenv on the operator's machine and install
this plugin's `requirements.txt` into it (the same three packages the README's "One-time
setup" step 3 names — `requests`, `PyYAML`, `openpyxl`):

```bash
python3 -m venv ~/.lv-sweep-venv
~/.lv-sweep-venv/bin/pip install -r "[plugin-root]/requirements.txt"
```

Record the absolute path to that venv's `bin/python` (`~/.lv-sweep-venv/bin/python` above) —
that is the interpreter the schedule below names. This failure mode is loud now (an import
error, in the log, with a banner), but it is still one step cheaper to avoid than to
diagnose after the fact.

## Step 2 — install the schedule

Pick whichever of the two your platform prefers. Both call the same wrapper with the same
three arguments, in this order: the plugin root, the venv python from Step 1, and the log
path.

### Option A — cron

Run `crontab -e` and add this line (fill in `[plugin-root]` and `[venv-python]` first):

```cron
0 */4 * * * /bin/sh "[plugin-root]/skills/backend-sweep/lv-sweep-run.sh" "[plugin-root]" "[venv-python]" "$HOME/Library/Logs/lv-backend-sweep.log"
```

Invoking through `/bin/sh` explicitly is deliberate: it does not depend on the executable
bit surviving a marketplace clone or an `rsync`. Do not "simplify" it away to a bare path.
The wrapper writes its own log (every stamp and notice line lands at the fourth argument
above), so no shell redirection is required on this line — cron's own stderr may still be
appended with `>>` if you want a second belt-and-braces record.

### Option B — launchd

Save as `~/Library/LaunchAgents/com.lightningvisuals.backend-sweep.plist` (fill in
`[plugin-root]` and `[venv-python]`), then load it with `launchctl load
~/Library/LaunchAgents/com.lightningvisuals.backend-sweep.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.lightningvisuals.backend-sweep</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>[plugin-root]/skills/backend-sweep/lv-sweep-run.sh</string>
    <string>[plugin-root]</string>
    <string>[venv-python]</string>
    <string>/Users/[operator-home-directory]/Library/Logs/lv-backend-sweep.log</string>
  </array>
  <key>StartInterval</key>
  <integer>14400</integer>
</dict>
</plist>
```

The wrapper writes its own log through the fourth `ProgramArguments` entry above, so no
`StandardOutPath` / `StandardErrorPath` key is required (either may still be added for
launchd's own stderr). Prefer Option A (cron) unless your platform already manages other
launchd agents.

## A trigger that cannot run is now loud — and what still stays silent

**If the trigger runs and cannot complete, it says so.** `lv-sweep-run.sh` posts a banner
naming itself as broken and exits non-zero on every failure path — the wrong number of
arguments, the python failing to run at all, or output it cannot parse. Broken and healthy
are no longer indistinguishable the way the earlier, silently-failing headless-LLM design
left them.

**A trigger that was never installed is still silent** — nothing runs, so nothing can post
a banner about not running. That residual case is honest, and it is exactly why Step 2
above exists: if notices are expected but never arrive, checking whether the schedule was
ever installed is the first thing to do, not the backend.

## Cadence: every 4 hours, and why

Both options above fire **every 4 hours** (`0 */4 * * *` / `StartInterval` `14400`
seconds). That is often enough that a stuck lock or an exhausted quota is caught within a
working day, and rare enough that it costs nothing to leave running around the clock.

**This is not free at any frequency, and the reasoning has to say so.** Every sweep fire
POSTs to `hubspot/backend-status`, and that endpoint's own docstring records that it
**probes all three provider balance endpoints unconditionally** on every call — it takes
no request body, so it has no way to know which providers a caller cares about. These are
**balance** endpoints, not match or enrich endpoints, so no enrichment credit is consumed
by a sweep fire today. But that fact depends on what the backend endpoint currently does,
not on anything structural in this client the way the read-only import guard is — if a
provider ever starts metering balance checks, **cadence is the only dial that limits the
cost**, which is why it is worth choosing deliberately here rather than discovering it on
a bill. Raise the interval if a slower cadence still catches problems fast enough for your
operator; do not lower it below what this reasoning assumes without re-reading it.

## Confirming it fired

Check `~/Library/Logs/lv-backend-sweep.log` after the next scheduled time passes:

- A **healthy** fire appends exactly one stamped line — `LV sweep ran, backend healthy, no
  notices.` — and nothing else.
- A fire **with notices** appends the notice count, the full JSON (untruncated), and one
  line per banner posted. The banner is gated on that notice list being non-empty — an
  empty list is the healthy case above, and posts no banner at all.
- A **broken** trigger appends a failure line, and by the time you open the log you have
  already seen a banner naming the sweep itself as broken.

## Uninstalling

Cron: `crontab -e` and delete the line. Launchd: `launchctl unload
~/Library/LaunchAgents/com.lightningvisuals.backend-sweep.plist` then delete the plist
file. Nothing else needs removing — `lv-sweep-run.sh` is a tracked file the plugin ships,
not something either step above created on the operator's machine beyond the venv and the
schedule entry itself.
