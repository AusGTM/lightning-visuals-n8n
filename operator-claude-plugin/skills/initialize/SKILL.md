---
name: initialize
description: Set this plugin up, or check whether it is already set up. Use when the operator has just installed the plugin, asks how to configure it, asks where the settings or config file is, says something is not working because it is not set up, is told by another skill that a value is missing, or asks whether setup is complete — or invoke it directly as /operator-claude-plugin:initialize.
---

# Initialize

> **Where commands run:** every `python3 scripts/...` line below runs from the **plugin
> root** — the directory that contains both `scripts/` and `skills/`, i.e. two levels up
> from this SKILL.md. `cd` there first. When the plugin is installed (not a repo
> checkout), that is the versioned plugin-cache directory this file lives under. Running
> from anywhere else fails with `No such file or directory` — found live by the 29-01
> headless probe, which lost a step to exactly this.


**This skill never asks for, receives, or displays a secret.** It reports which settings are
still needed and where the file is. The operator types values into that file, never into
this conversation — a secret pasted into a chat is in the transcript forever.

Safe to run any number of times. It changes nothing when setup is already complete.

## Step 1 — check the current state

```
python3 scripts/init_check.py
```

Read its output back to the operator in your own words. It prints one of four states.

**Already set up.** Say so plainly and stop. Do not offer to re-do it, do not print the
file's contents, do not suggest they verify the values — there is nothing to check that
this command has not already checked. Also relay the settings-file location line
`init_check.py` printed — it is reassurance about the settings surviving a plugin update,
not something the operator needs to act on. Tell them what they can now do (upload
contacts, ask for backend status, triage the review queue) and end there.

**No settings file yet.** Offer to put the template in place:

```
python3 scripts/init_check.py --create
```

That copies a template of placeholders — it never overwrites an existing file, and it
writes no secret because it has none. Then continue to step 2.

**File exists, values still needed.** Go to step 2. This is also what you see when the
template is in place but not yet filled in.

**File cannot be read.** Usually a missing comma or quote from hand-editing. Give them the
path and say they can either fix it or delete it and start again from the template. Do not
attempt to repair the JSON yourself unless they ask — a settings file you rewrote is one
they no longer trust.

## Step 2 — tell them exactly what to do

Give them, in this order:

1. **The full path** to the settings file, exactly as `init_check.py` printed it. Do not
   paraphrase it or describe it as "in the config folder" — the whole reason this skill
   exists is that they cannot be expected to know where the plugin was installed. That
   path is now version-independent — the same reason the instruction insists on relaying
   it verbatim in the first place hasn't changed, it just now also survives an update.
2. **Which values are still needed**, by name, and that both come from **their n8n admin**:
   - `n8n_url` — the `https://` address of the n8n instance.
   - `webhook_secret` — the shared secret the backend checks on every request.
   - `n8n_api_key` — only needed for reading backend status and turning jobs on and off.
3. **That they type these into the file, not to you.**

Then say what each missing value costs them, using the capability lines the command
printed. Do not say the plugin is "broken" when one capability is unconfigured — a config
with no `n8n_api_key` still uploads contacts perfectly well, and over-refusing is exactly
what PLUGIN-03 forbids.

## Step 3 — confirm

When they say they have filled it in, run step 1 again. Report the result. If a value is
still showing as a placeholder, say which one and that the template text is still in there
— that is the common miss, because the file looks filled in at a glance.

## What this skill must never do

- **Never ask the operator to tell you a secret**, and never repeat one back if they paste
  one anyway. If they do paste one, tell them plainly that it is now in the conversation
  history, that they should put it in the file themselves, and that they may want to have
  it rotated.
- **Never print the contents of the settings file.**
- **Never guess a value.** An invented `n8n_url` produces an auth error three steps later
  that nobody traces back to here.
