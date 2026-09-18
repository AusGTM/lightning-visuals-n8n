---
name: loss-reason-report
description: Build a report of why closed-lost deals were lost, cross-tabulated against the lost company's ICP tier and score, so the operator can see patterns like "we lose Tier A deals on price." Use when the operator asks why deals are being lost, asks about closed-lost reasons, asks whether the ICP rubric matches actual loss outcomes, or wants to see loss reasons broken down by tier — or invoke it directly as /operator-claude-plugin:loss-reason-report.
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

# Loss-Reason Report

> **Where commands run: this is different from every other skill in this plugin.** The
> command below runs from the **backend repo checkout root** — the directory that
> contains both `scripts/` and `src/` (`lv-n8n-poc/` in this operator's setup) — not from
> the plugin root the way every other skill's commands do. `cd` there first. **If that
> checkout is not present on this machine, say so plainly and stop.** Do not guess a
> path, and do not try another directory — this skill has exactly one place it can run
> from, and a report built from the wrong place is a report you did not actually build.

**This skill reads. It changes nothing.** The report it builds is consumption only — it
never writes a HubSpot property, never touches a rubric weight in
`config/icp_scoring.yaml`, and never invents a reason a deal was lost. If the report says
zero loss reasons were found, tell the operator zero were found. Never fill that gap with
a guess about why deals are being lost.

**This skill never imports backend code.** Its entire mechanism is running the
repo-root aggregator (`scripts/build_loss_reason_report.py`) as a subprocess and reading
back the markdown file it writes — the same separation every other skill in this plugin
keeps from the n8n webhook surface, extended here to a backend script instead of an
HTTP call. This plugin holds no HubSpot credential and gains none from this skill.

## Steps

1. **Confirm the backend repo checkout is present**, from the "Where commands run" note
   above. If it is not, tell the operator this report needs a checkout of the backend
   repo on this machine and stop — there is nothing else to try.

2. **Run the aggregator with HubSpot credentials sourced from the backend repo's own
   `.env` file.** This is the one command in this skill, and it needs a credential
   prelude no other skill's command carries — copying a bare `python3 scripts/...` line
   from another skill ships a command that fails on its very first real use with a
   missing-credentials message, because the aggregator deliberately does not load
   `.env` itself (this repo's own convention):

   ```
   set -a; . ./.env; set +a; python3 scripts/build_loss_reason_report.py
   ```

3. **Read the exit code before anything else.**

   - **Exit 0** — the aggregator looked at HubSpot and wrote a report. This is true
     whether it found ten loss reasons or none; an empty result is a normal, complete
     answer, not a partial one.
   - **Non-zero with a message starting `skipped (no credentials)`** — the aggregator
     never reached HubSpot at all. Say exactly that: this run did not look, so there is
     no finding to report — not "zero loss reasons," not "nothing to show." Relay the
     printed message and stop. Never present a run that could not look as a run that
     looked and found nothing.
   - **Non-zero with a message starting `REFUSED`** — the configured `HUBSPOT_PORTAL_ID`
     does not match the portal this report is scoped to. Relay the message and stop.

4. **Read the report file the command printed** (`wrote docs/reports/<date>-loss-reason-
   report.md`) and relay it to the operator in plain language, keeping the same
   distinctions the report itself draws:

   - Whether each of the two loss-reason properties (`lv_closed_lost_reason` and
     HubSpot's native `closed_lost_reason`) **does not exist in this portal** versus
     **exists and is 0% filled** versus **exists and is partially filled** — these are
     three different facts, say which one is true, never round the first two together.
   - The counts of closed-lost deals examined, how many carried a loss reason, and how
     many of those joined to a company via the primary association versus the
     Associations v4 fallback versus not at all.
   - The loss-reason-by-tier table, when one exists. If the operator asks "are we losing
     good-fit deals," this table is the answer — read it as-is, and do not summarize away
     an "Unknown" tier row; it means a deal that could not be joined to a company, not
     zero deals.

5. **If the operator asks for a change based on what the report shows** (a rubric weight,
   a new loss-reason value, a process change), say plainly that this skill only reports —
   changing the rubric is a separate, deliberate decision outside this skill's scope, made
   the same way every other rubric change in this project is made, not something this
   report can trigger on its own.

## What this skill never asks the operator to do

Paste a secret, edit `.env`, or set an environment variable by hand — the credential
prelude in step 2 sources the backend repo's existing `.env` file, it does not ask the
operator to supply anything new. If that file is missing or the aggregator still reports
no credentials after sourcing it, say so and name the backend repo's own `.env` setup as
the place to fix it — this skill cannot create or edit that file.
