---
name: initialize
description: Set this plugin up, or check whether it is already set up. Use when the operator has just installed the plugin, asks how to configure it, asks where the settings or config file is, says something is not working because it is not set up, is told by another skill that a value is missing, or asks whether setup is complete — or invoke it directly as /operator-claude-plugin:initialize.
---

<!-- CRM-ACCESS-BLOCK v1 (D-14a/D-14b/D-14d, D-15a/D-15b/D-15c/D-15d) -->
<!-- Canonical source: operator-claude-plugin/config/crm_access_block.md -->
<!-- Do not edit this block inside a SKILL.md. Edit the canonical file above and copy it -->
<!-- verbatim into every skill; test_crm_access_block.py pins that every copy matches. -->

**Before any HubSpot access this session, read this.**

**Portal rule (D-14a).** Any HubSpot tool outside this plugin's own lanes — the claude.ai
HubSpot connector, an MCP HubSpot server, the `hs` CLI — must prove IT is on portal
`22617666` before its first call this session, read or write. The proof is that tool
looking up, through itself, a record this plugin knows exists: an `hs_object_id` from
`written_records`, or the configured sentinel id. Zero results is the lookup proof
failing — it means the wrong portal: stop the step and say so, naming the portal the
plugin expects and the record that was not found. Do not retry, do not fall back to a
plugin lane silently, and do not treat a zero result as "the record does not exist." The
2026-09-18 session's connector was on a different portal and returned zero results for
contacts the plugin had just created — this rule exists to stop exactly that. This rule
is skill text the assistant follows when reading this skill; there is no runtime hook
and no code gate enforcing the portal proof.

**Connector-write rule (D-14b).** A write through such a tool, once its portal is
proven, is under the SAME session grant as every other write path: call
`write_grant.covers()` before it, append the outcome to `written_records` with
`source: connector`, and associate a created contact to its company in the same step,
exactly as the ingest lane does. One yes governs all paths.

**Session-grant rule (D-15a/b/c/d).** The first yes covers the whole session — every
lane, and the domains and ids named in that proposal. Every later send goes through
`covers()` on that one grant. A send outside its record set widens the grant with
`widen()` and STATES the widening; it never asks again and never opens a second grant.
Opening a second grant while one is already open is refused by the code, naming the
open grant. The ask itself is one sentence: this yes covers every send this session across the
named lanes for the named domains, widening as new domains appear, and the operator may
say revoke at any time (`CLOSED_REVOKED`).

<!-- END CRM-ACCESS-BLOCK -->

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
2. **Which values are still needed**, by name, and that all three come from **their n8n admin**:
   - `n8n_url` — the `https://` address of the n8n instance.
   - `webhook_secret` — the shared secret the backend checks on every request.
   - `n8n_api_key` — the n8n API key (a different secret from `webhook_secret`). Needed by
     every lane that sends a batch — uploads, enrichment, matching — as well as backend
     status and turning jobs on and off, because a batch's per-record outcome is read back
     from n8n's execution record (`config_gate.CAPABILITY_KEYS`, D-70-10).
3. **That they type these into the file, not to you.**

Then say what each missing value costs them, using the capability lines the command
printed.

Relay the **optional settings** block too, exactly as `init_check.py` printed it. It is a
separate block from the capability lines on purpose: those say which keys are present,
while a setting says an admin *authorized* something. A setting that is off is not a fault
and must never be reported as one — it is a switch nobody has needed yet. Do not say the plugin is "broken" when one capability is unconfigured — a config
with no `webhook_secret` still answers the backend status check, and over-refusing is exactly
what PLUGIN-03 forbids. (Since D-70-10 a config with no `n8n_api_key` cannot upload
contacts either — every send-capable lane needs it — so name that consequence plainly.)

## Step 3 — confirm

When they say they have filled it in, run step 1 again. Report the result. If a value is
still showing as a placeholder, say which one and that the template text is still in there
— that is the common miss, because the file looks filled in at a glance.

## If they ask to let operators authorize HubSpot writes

An admin who wants operators to be able to turn live HubSpot writes on from a conversation
sets one key in the same settings file:

```json
"allow_write_grants": true
```

It must be the JSON boolean `true`. The string `"true"`, `1` and `"yes"` all read as **not
authorized**, by design. Absent means off, which is why an older settings file simply
reports the setting as off rather than as missing something.

Say plainly what setting it does and does not do. **It does:** let an operator name a batch,
see the worst-case spend, say yes once, and have each send in that batch arm live writes for
exactly the records in the grant. **It does not:** turn on unattended writing. Every send is
still bounded to a named record set, the arithmetic is still shown before the yes, and writes
are still disarmed after every send. And it does **not** replace `ALLOW_N8N_ARM` — that
environment variable is still the sole authority for the headless and cron paths, which have
no operator to confirm anything. The two are not alternatives.

## What this skill must never do

- **Never ask the operator to tell you a secret**, and never repeat one back if they paste
  one anyway. If they do paste one, tell them plainly that it is now in the conversation
  history, that they should put it in the file themselves, and that they may want to have
  it rotated.
- **Never print the contents of the settings file.**
- **Never guess a value.** An invented `n8n_url` produces an auth error three steps later
  that nobody traces back to here.
