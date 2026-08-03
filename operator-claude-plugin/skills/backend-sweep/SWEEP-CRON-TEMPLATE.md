# Sweep Trigger Template — cron / launchd

**Audience: an admin, installing this on the operator's machine. Not the operator.** The
operator never opens a terminal, edits a config file, or runs a command — that rule holds
everywhere else in this plugin and holds here too. Nothing in this file is ever handed to
the operator to run themselves.

## What this installs, and why it is a second step

Installing this plugin does **not** install this trigger. The plugin ships the sweep's
*logic* (`scripts/sweep_entry.py`, the `backend-sweep` skill); this file is the *trigger*
that fires it on a schedule with no session open — a machine-local `cron`/`launchd` entry
running `claude -p` headlessly. That entry lives outside the plugin's own packaging (it is
not a git-tracked file the plugin ships), so it has to be installed on purpose, by an
admin, as an explicit second step. A plugin installed without this step is a sweep that
never fires — silently, because a sweep that never fires and a healthy backend look
identical from the operator's side (this is a known, accepted gap, tracked separately;
this file's job is only to make sure the trigger gets installed, not to close that gap).

This reproduces the exact invocation `29-HOST-PROBE.md` §A1 confirmed working — a
different, approximate invocation is the failure that probe existed to prevent — and the
delivery mechanics §A5 recorded: a one-line macOS Notification Center banner via
`osascript`, with full detail redirected to a log file, because the banner budget is one
short line and the log is where the rest survives.

## Step 1 — save the sweep prompt

Save this exact text to `~/.claude/lv-sweep-prompt.txt` (create the `~/.claude/`
directory first if it does not already exist):

```text
Run the operator-claude-plugin's backend-sweep skill now, and use no other tool beyond
what that skill's own steps call for. It returns a JSON list of notice objects, or an
empty list.

If the list is empty: print exactly one line — "LV sweep ran, backend healthy, no
notices." — and stop there. Do not print anything else, do not summarize the backend's
state, and do not add a healthy-report line of your own. Silence is the answer; the one
line above is only a run stamp proving the cron fired, not a report.

If the list is NOT empty: print the full JSON list first, so the redirected log keeps
every notice's complete detail untruncated. Then, for every notice in that list, run
exactly one command:

osascript -e 'display notification "<notice headline, verbatim>" with title "LV Backend Sweep"'

using that notice's own headline text exactly as given, with no rewording and no
combining more than one notice into a single line. Post one notification per notice.

Never run any command other than the skill's own read, the one-line run stamp above, or
the osascript call above. This is a read-only, unattended sweep: no write to HubSpot, no
write to n8n, no dispatch, no arm, ever — if anything here looks like it would write,
stop and do not run it.
```

## Step 2 — install the schedule

Pick whichever of the two your platform prefers. Both reproduce the same invocation.

### Option A — cron

Run `crontab -e` and add this line (fill in the two bracketed paths first — find the
`claude` binary with `which claude`):

```cron
0 */4 * * * cd "$HOME" && [path-to-claude-binary] -p "$(cat "$HOME/.claude/lv-sweep-prompt.txt")" --allowedTools "Skill,Bash,Read,Glob,Grep" >> "$HOME/Library/Logs/lv-backend-sweep.log" 2>&1
```

### Option B — launchd

Save as `~/Library/LaunchAgents/com.lightningvisuals.backend-sweep.plist` (fill in
`[path-to-claude-binary]`), then load it with `launchctl load ~/Library/LaunchAgents/com.lightningvisuals.backend-sweep.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.lightningvisuals.backend-sweep</string>
  <key>ProgramArguments</key>
  <array>
    <string>[path-to-claude-binary]</string>
    <string>-p</string>
    <string>PROMPT_PLACEHOLDER</string>
    <string>--allowedTools</string>
    <string>Skill,Bash,Read,Glob,Grep</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/[operator-home-directory]</string>
  <key>StartInterval</key>
  <integer>14400</integer>
  <key>StandardOutPath</key>
  <string>/Users/[operator-home-directory]/Library/Logs/lv-backend-sweep.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/[operator-home-directory]/Library/Logs/lv-backend-sweep.log</string>
</dict>
</plist>
```

`launchd`'s `ProgramArguments` array cannot run a shell `$(cat ...)` substitution the way
cron can — replace `PROMPT_PLACEHOLDER` with the literal contents of
`~/.claude/lv-sweep-prompt.txt` from Step 1, pasted in as one XML string value. Prefer
Option A (cron) unless your platform already manages other launchd agents; it needs no
manual copy-paste of the prompt text into a second file.

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

Check `~/Library/Logs/lv-backend-sweep.log` after the next scheduled time passes. A
healthy fire prints exactly the one run-stamp line from the prompt above; nothing else
appearing in the log on a healthy day is itself a signal something is misconfigured
upstream (the prompt, the skill, or the cron entry itself), not that the sweep found nine
things wrong.

## Uninstalling

Cron: `crontab -e` and delete the line. Launchd: `launchctl unload
~/Library/LaunchAgents/com.lightningvisuals.backend-sweep.plist` then delete the plist
file. Either way, deleting `~/.claude/lv-sweep-prompt.txt` is optional — an admin re-running
Step 1 later can just overwrite it.
