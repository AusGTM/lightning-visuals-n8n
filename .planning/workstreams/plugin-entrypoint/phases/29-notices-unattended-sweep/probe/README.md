# RB-2 / 29-01 probe — run this on the OPERATOR's machine

The operator is not on the machine this repo was developed on, so nothing here assumes a
path under anyone's home directory. Everything the probe needs is in this folder.

**What it answers:** can a scheduled Claude routine invoke this plugin's own read-only
status skill, does real backend data come back, and where does the output surface. Those
three answers are what 29-03/04/05/06 are built on, which is why the probe exists before
the code rather than after it.

**Why a human runs it:** the deliverable is an observation of the Desktop UI — whether a
banner appeared, whether output was truncated. A routine's cadence is stored inside the
app, not in any file, so there is no way to schedule one or make it fire from a terminal.

---

## 0. Install the plugin (once, on the operator's machine)

In Claude Code:

```
/plugin marketplace add <this-repo-url-or-local-path>
/plugin install operator-claude-plugin@lightning-visuals-operator
```

Or in Claude Desktop, use the plugin manager — that is the path PLUGIN-01 is written
against and the one 23-06 A2 verified.

Then do the one-time config in `operator-claude-plugin/README.md` § "One-time setup":
copy `config/operator.local.example.json` to `config/operator.local.json` and fill in
`n8n_url` and `webhook_secret` from your n8n admin.

**Check it worked** before scheduling anything — in a normal session run:

```
/operator-claude-plugin:backend-status
```

If that does not resolve, stop: the probe would return a NO for a trivial reason and waste
the cycle. Fix the install first.

## 1. Drop the routine in

Copy `lv-sweep-probe-SKILL.md` to your scheduled-routines folder, as
`SKILL.md` inside a folder named for the routine:

```
~/Documents/Claude/Scheduled/lv-sweep-probe/SKILL.md
```

(That is the location on macOS, alongside any existing routine you already have.)

## 2. Schedule it, once

In Claude Desktop, set `lv-sweep-probe` to the **soonest cadence the UI offers** and let it
fire **one** time.

## 3. Record three things

1. **Did the routine reach the plugin's skill?** YES / NO / TRIED-AND-ERRORED — if it
   errored, the error text **verbatim**.
2. **Did real backend data come back**, or only a description of what it would have
   fetched? Named workflows, on/off states, a queue count = real. Generic prose = narration,
   which counts as a NO. The routine is written to mark itself `NO-ONLY-NARRATION` when it
   narrates, but check it rather than trusting it.
3. **Where did the output surface** — notification banner, in-app inbox, both, somewhere
   else — and roughly how much rendered before truncation. The routine ends with
   `END OF PROBE OUTPUT`; if that line is missing, it was truncated, and roughly where
   matters because it sets the ceiling 29-05 formats against.

## 4. Delete the routine

It is a throwaway. `29-01` Task 1 step 4 requires removing it so no unattended routine
outlives the probe (T-29-01).

---

## If the answer is NO

**That is a complete, useful answer and the phase pre-authorises it.** Do not work around
it. A negative result stops Phase 29 and routes to D-01b's named fallback (Managed Agents
`deployments`), which is a different phase shape and needs the operator's decision, not a
planner's workaround.

## What to send back

Paste the whole `LV-SWEEP-PROBE RESULT` block plus the three observations above. That is
what gets written into `29-HOST-PROBE.md`, which four plans then read.
