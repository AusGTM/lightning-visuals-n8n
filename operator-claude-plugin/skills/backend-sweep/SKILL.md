---
name: backend-sweep
description: Run one unattended read of the HubSpot enrichment backend and report back only what needs a human's attention — a failed scheduled run, a credential or quota failure, a stuck lock, or a review backlog past its threshold — or nothing at all when the backend is healthy. This is the skill an unattended scheduled routine invokes on a cadence; the operator never needs to ask for it by name, though it can be run on demand as /operator-claude-plugin:backend-sweep to see exactly what the next unattended fire would report.
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

# Backend Sweep

> **Where commands run:** the one command below runs from the **plugin root** — the
> directory that contains both `scripts/` and `skills/`, i.e. two levels up from this
> SKILL.md. `cd` there first. When the plugin is installed (not a repo checkout), that is
> the versioned plugin-cache directory this file lives under.

**This skill reads. It changes nothing, ever.** Its entire job is to run the sweep
entrypoint and hand back exactly what it returns — nothing else. It names one script and
nothing beyond it. Do not extend this skill to also check something else, dispatch a
batch, retry a run, or arm anything — widening what this skill reaches is a NOTICE-05
violation, and `tests/test_sweep_read_only.py` exists to catch exactly that widening
before it ships.

## Steps

1. Run:

   ```
   python3 scripts/sweep_entry.py
   ```

   This prints one JSON value: a list of notice objects, or `[]`. There is nothing else
   to run and nothing else to check — the sweep already read everything it watches
   (`sweep_read.gather`) and already decided what fired (`sweep_conditions.evaluate`).
   If the config is missing the keys this capability needs, the same command prints a
   single admin-attributed notice saying so — it never raises, and it is not silence.

2. **If the list is `[]`, the whole answer is silence.** Say nothing further — do not
   report "backend healthy" or manufacture any other all-clear line. Silence IS the
   answer (NOTICE-04). Inventing a healthy-report line is exactly the noise that trains
   an operator, or an unattended cron wrapper's log, to start ignoring this sweep.

3. **If the list has one or more notice objects, hand them back verbatim** — each one's
   `headline`, `detail`, and `who_can_fix`. Do not summarise, merge, or reword them: they
   already carry the one-line banner budget and the full log detail, already attributed
   to the operator or an admin. Do not add advice of your own beyond what `detail`
   already says.

This skill never turns anything on or off, starts, stops, or retries a run, or writes to
any record — the same posture as `backend-status`, enforced the same way: nothing this
skill reaches has a code path to a mutation.
